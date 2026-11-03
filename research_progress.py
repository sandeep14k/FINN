"""Small, atomic progress records shared by Python jobs and the Node API."""
import json
import os
import time
from datetime import datetime, timezone
from config import DATA_DIR
from storage import atomic_json


def set_progress(symbol, stage, status='running'):
    directory = DATA_DIR / '.jobs'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'{symbol}.json'
    try:
        previous = json.loads(target.read_text())
    except (FileNotFoundError, ValueError):
        previous = {}
    pid = int(os.getenv('FINN_JOB_PID', str(os.getpid())))
    started = int(os.getenv('FINN_JOB_STARTED', str(previous.get('started') if previous.get('pid') == pid else int(time.time() * 1000))))
    if os.getenv('FINN_JOB_ID') and status == 'ready':
        status = 'running'  # The supervisor owns final publication and completion.
    atomic_json(target, {'status': status, 'stage': stage, 'started': started,
                        'pid': pid, 'run_id': os.getenv('FINN_JOB_ID'),
                        'updated_at': datetime.now(timezone.utc).isoformat()})
