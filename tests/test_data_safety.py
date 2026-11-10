import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from scripts.training_data_guard import validate_training_inputs


def record(question, answer='Câu trả lời'):
    return {'prompt': [{'role': 'user', 'content': question}],
            'completion': [{'role': 'assistant', 'content': answer}]}


class DataSafetyTests(unittest.TestCase):
    def test_heldout_prompt_cannot_be_trained_even_with_a_changed_answer(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, row in [('train', record('Câu hỏi test', 'Đáp án khác')),
                              ('validation', record('Câu hỏi validation')),
                              ('test_external', record('Câu hỏi test'))]:
                (root/(name+'.jsonl')).write_text(json.dumps(row), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'held-out prompts'):
                validate_training_inputs(root/'train.jsonl', root/'validation.jsonl')

    def test_same_path_and_heldout_filename_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_training_inputs('test_external.jsonl', 'validation.jsonl')
        with self.assertRaises(ValueError):
            validate_training_inputs('train.jsonl', 'train.jsonl')

    def test_generator_preserves_existing_data(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as folder:
            train = Path(folder)/'train.jsonl'
            train.write_bytes(b'old data must remain')
            result = subprocess.run([sys.executable, '-m', 'scripts.make_train_data', '--output', folder],
                                    cwd=root, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(train.read_bytes(), b'old data must remain')
            self.assertFalse((Path(folder)/'validation.jsonl').exists())


if __name__ == '__main__':
    unittest.main()
