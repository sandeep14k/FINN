"""Exercise real process cleanup and final publication without external requests."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import research_job


class JobTests(unittest.TestCase):
    def test_timeout_stops_descendants_and_preserves_saved_research(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / 'data'
            data.mkdir()
            saved = root / 'finn-app/public/data/pull/TEST.json'
            saved.parent.mkdir(parents=True)
            saved.write_text('{"previous": true}')
            (root / 'run_pull.py').write_text("import subprocess,sys,time\nfrom pathlib import Path\np=subprocess.Popen([sys.executable,'-c',\"import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)\"])\nPath('child.pid').write_text(str(p.pid))\ntime.sleep(60)\n")
            with patch.object(research_job, 'ROOT_DIR', root), patch.object(research_job, 'DATA_DIR', data):
                with self.assertRaises(subprocess.TimeoutExpired):
                    research_job.run_job('TEST', timeout=1)
            child = int((root / 'child.pid').read_text())
            state = subprocess.run(['ps', '-o', 'stat=', '-p', str(child)], capture_output=True, text=True).stdout.strip()
            self.assertTrue(not state or state.startswith('Z'), state)
            self.assertEqual(json.loads(saved.read_text()), {'previous': True})
            self.assertEqual(json.loads((data / '.jobs/TEST.json').read_text())['status'], 'failed')

    def test_success_publishes_sources_before_ready(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = root / 'data'
            data.mkdir()
            (root / 'run_pull.py').write_text("import os,json\nfrom pathlib import Path\np=Path(os.environ['FINN_PUBLIC_DATA_DIR'])\n(p/'pull').mkdir(parents=True)\n(p/'docs/TEST').mkdir(parents=True)\n(p/'docs/TEST/call.json').write_text('[{\"page\":1,\"text\":\"Evidence\"}]')\n(p/'pull/TEST.json').write_text('{\"symbol\":\"TEST\",\"metrics\":[]}')\n")
            with patch.object(research_job, 'ROOT_DIR', root), patch.object(research_job, 'DATA_DIR', data):
                research_job.run_job('TEST', timeout=5)
            self.assertTrue((root / 'finn-app/public/data/docs/TEST/call.json').exists())
            self.assertEqual(json.loads((data / '.jobs/TEST.json').read_text())['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
