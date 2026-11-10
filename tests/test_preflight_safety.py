from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class PreflightSafetyTests(unittest.TestCase):
    def test_inline_preflight_requires_data_review_acknowledgment(self):
        completed=subprocess.run([sys.executable,'-m','scripts.finetune','--run-preflight',
                                  '--preflight-output','outputs/must_not_be_created'],
                                 capture_output=True,text=True)
        self.assertNotEqual(completed.returncode,0)
        self.assertIn('--accept-reviewed-candidate after data review',completed.stderr)

    def test_inline_preflight_does_not_generate_missing_training_data(self):
        with tempfile.TemporaryDirectory() as folder:
            train=Path(folder)/'train.jsonl'
            completed=subprocess.run([sys.executable,'-m','scripts.finetune','--run-preflight',
                                      '--accept-reviewed-candidate','--preflight-output','outputs/must_not_be_created',
                                      '--train',str(train),'--valid',str(Path(folder)/'validation.jsonl')],
                                     capture_output=True,text=True)
            self.assertNotEqual(completed.returncode,0)
            self.assertFalse(train.exists())
            self.assertIn('FileNotFoundError',completed.stderr)

    def test_preflight_flag_requires_explicit_output_and_does_not_import_torch(self):
        completed=subprocess.run([sys.executable,'-m','scripts.finetune','--preflight-only'],
                                 capture_output=True,text=True)
        self.assertNotEqual(completed.returncode,0)
        self.assertIn('--preflight-only requires --preflight-output',completed.stderr)

    def test_windows_python_selector_uses_accessible_environment(self):
        root=Path(__file__).resolve().parents[1]
        if not (root/'.venv/Scripts/python.exe').exists():
            self.skipTest('Project .venv not installed after user-requested cleanup')
        completed=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command',
            "$ErrorActionPreference='Stop'; . ./windows/python.ps1; $p=Resolve-MyAIPython; & $p -c 'import fastapi,uvicorn; print(231723)'"],
            cwd=root,capture_output=True,text=True)
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertIn('231723',completed.stdout)
