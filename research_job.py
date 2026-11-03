"""Own a research run, its child tree, exclusive lock and final publication."""
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from uuid import uuid4
from config import ROOT_DIR, DATA_DIR
from storage import atomic_json


def stop_tree(process):
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_job(symbol, evidence_only=False, timeout=1800):
    symbol = symbol.upper().removesuffix('.NS')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&-]{0,24}', symbol):
        raise ValueError('Invalid NSE symbol')
    jobs = DATA_DIR / '.jobs'
    jobs.mkdir(parents=True, exist_ok=True)
    with open(jobs / 'research.lock', 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another company is being researched. Please retry shortly.') from None
        run_id, started = uuid4().hex, int(time.time() * 1000)
        stage = jobs / run_id / 'public'
        stage.mkdir(parents=True)
        env = {**os.environ, 'FINN_JOB_ID': run_id, 'FINN_JOB_PID': str(os.getpid()),
               'FINN_JOB_STARTED': str(started), 'FINN_PUBLIC_DATA_DIR': str(stage)}
        record = {'run_id': run_id, 'pid': os.getpid(), 'started': started}
        process = None
        def interrupted(_signal, _frame):
            raise InterruptedError('Research interrupted')
        handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT)}
        atomic_json(jobs / f'{symbol}.json', {**record, 'status': 'running', 'stage': 'Starting research'})
        try:
            command = [sys.executable, 'run_pull.py', symbol, '--owned'] + (['--evidence-only'] if evidence_only else [])
            process = subprocess.Popen(command, cwd=ROOT_DIR, env=env, start_new_session=True)
            code = process.wait(timeout=timeout)
            if code:
                raise RuntimeError('Primary-source pipeline failed')
            result = json.loads((stage / 'pull' / f'{symbol}.json').read_text())
            dest = ROOT_DIR / 'finn-app/public/data'
            for source in (stage / 'docs' / symbol).glob('*.json'):
                atomic_json(dest / 'docs' / symbol / source.name, json.loads(source.read_text()))
            atomic_json(dest / 'pull' / f'{symbol}.json', result)
            atomic_json(jobs / f'{symbol}.json', {**record, 'status': 'ready', 'stage': 'Research ready'})
        except BaseException:
            stop_tree(process)
            atomic_json(jobs / f'{symbol}.json', {**record, 'status': 'failed', 'stage': 'Research failed; previous saved evidence retained'})
            raise
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            shutil.rmtree(stage.parent)


if __name__ == '__main__':
    run_job(sys.argv[1], '--evidence-only' in sys.argv)
