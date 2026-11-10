import json
from pathlib import Path
import tempfile
import unittest
from scripts.qwen_training_contract import tokenize_example,validate_launch_report,validate_resume_checkpoint


class TokenizerFixture:
    """Utility contract fixture only. Never used as evidence of Qwen token counts."""
    def apply_chat_template(self,messages,**kwargs):
        return [1,2,3] if len(messages)==1 else [1,2,3,8,9]


class QwenContractTests(unittest.TestCase):
    def test_prompt_and_completion_masks_and_truncation_detection(self):
        row={'prompt':[{'role':'user','content':'question'}],'completion':[{'role':'assistant','content':'answer'}]}
        example,stats=tokenize_example(TokenizerFixture(),row,5)
        self.assertEqual(example['labels'],[-100,-100,-100,8,9]);self.assertFalse(stats['completion_truncated'])
        example,stats=tokenize_example(TokenizerFixture(),row,3)
        self.assertTrue(stats['completion_lost']);self.assertTrue(stats['completion_truncated'])

    def test_blocked_preflight_cannot_start_training(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'report.json';path.write_text(json.dumps({'checks':{}}))
            with self.assertRaisesRegex(ValueError,'blocked'):
                validate_launch_report(path,'model','train','valid',1024)

    def test_config_only_adapter_is_not_a_resumable_training_checkpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);(path/'adapter_config.json').write_text('{}')
            with self.assertRaises(ValueError):validate_resume_checkpoint(path)
