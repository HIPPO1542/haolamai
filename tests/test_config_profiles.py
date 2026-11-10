"""Check Windows deployment profiles and default model consistency without CUDA."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

class WindowsProfileTests(unittest.TestCase):
    def test_powershell_profiles_are_explicit(self):
        for script in ("download", "train", "start", "evaluate"):
            contents=(ROOT/"windows"/(script+".ps1")).read_text(encoding="utf-8")
            self.assertIn('ValidateSet("high", "balanced")',contents)
            self.assertIn('"9B"',contents)
            self.assertIn('"4B"',contents)
    def test_no_old_model_defaults(self):
        for script in ("finetune.py", "download_model.py", "evaluate_adapter.py", "preflight.py"):
            self.assertNotIn("Qwen3-1.7B",(ROOT/"scripts"/script).read_text(encoding="utf-8"))
        for f in ("engine.py", "api.py"):
            self.assertNotIn("Qwen3-1.7B",(ROOT/"myai"/f).read_text(encoding="utf-8"))
    def test_windows_docs_not_require_ubuntu(self):
        doc=(ROOT/"README_Windows.md").read_text(encoding="utf-8")
        self.assertIn("KHÔNG Ubuntu",doc)
        self.assertIn("nvidia-smi",doc)

if __name__=='__main__':unittest.main()
