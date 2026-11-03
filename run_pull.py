"""Run primary-source research; degrade explicitly to excerpts if analysis fails."""
import os
import re
import subprocess
import sys
from pathlib import Path
from config import ROOT_DIR
from evidence_research import publish_evidence
from research_progress import set_progress


def run_pipeline(symbol: str, evidence_only=False):
    symbol = symbol.upper().removesuffix('.NS')
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9&-]{0,24}', symbol):
        raise ValueError('Invalid NSE symbol')
    set_progress(symbol, 'Discovering annual reports and earnings-call transcripts')
    subprocess.run([sys.executable, 'ingest_ticker.py', symbol], check=True, cwd=ROOT_DIR)
    if evidence_only or not os.getenv('GROQ_API_KEY'):
        publish_evidence(symbol)
        set_progress(symbol, 'Primary-source excerpts ready', 'ready')
        return
    steps = ['label_docs.py', 'snapshot.py', 'guidance_extract.py', 'promised_vs_delivered.py', 'ground.py']
    for script in steps:
        set_progress(symbol, {
            'label_docs.py': 'Identifying reporting periods',
            'snapshot.py': 'Reading the annual report',
            'guidance_extract.py': 'Extracting guidance and reported results',
            'promised_vs_delivered.py': 'Matching promises to reporting periods',
            'ground.py': 'Verifying quotations and publishing research',
        }[script])
        print(f'Running {script} for {symbol}', flush=True)
        result = subprocess.run([sys.executable, script, symbol], cwd=ROOT_DIR, capture_output=True, text=True)
        if result.returncode:
            print(f'{script} failed. Publishing primary-source excerpts without a model verdict.', flush=True)
            # Preserve detailed diagnostics server-side; never send prompts or secrets to clients.
            print(result.stderr[-3000:], file=sys.stderr)
            publish_evidence(symbol)
            set_progress(symbol, 'Primary-source excerpts ready; model analysis unavailable', 'ready')
            return
        print(result.stdout, flush=True)
    from research_brief import publish_brief
    set_progress(symbol, 'Building the company research brief')
    publish_brief(symbol, use_model=True)
    set_progress(symbol, 'Research ready', 'ready')

if __name__ == '__main__':
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'INFY'
    if '--owned' not in sys.argv:
        from research_job import run_job
        run_job(symbol, '--evidence-only' in sys.argv)
        sys.exit(0)
    try:
        run_pipeline(symbol, '--evidence-only' in sys.argv)
    except Exception:
        safe = symbol.upper().removesuffix('.NS')
        if re.fullmatch(r'[A-Z0-9][A-Z0-9&-]{0,24}', safe):
            set_progress(safe, 'Research failed; prior saved evidence is retained', 'failed')
        raise
