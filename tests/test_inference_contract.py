"""Check tokenizer/generate argument plumbing without importing CUDA or weights."""
from contextlib import nullcontext
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from myai.engine import LocalQwen


class InferenceContractTests(unittest.TestCase):
    def test_chat_template_mapping_passes_attention_mask_to_generate(self):
        model = LocalQwen()
        input_ids = Mock()
        input_ids.shape = (1, 3)
        input_ids.to.return_value = input_ids
        attention_mask = Mock()
        attention_mask.to.return_value = attention_mask
        model._tokenizer = Mock(eos_token_id=2)
        model._tokenizer.apply_chat_template.return_value = {'input_ids': input_ids, 'attention_mask': attention_mask}
        model._tokenizer.decode.return_value = 'Câu trả lời từ fixture'
        model._model = Mock()
        model._model.parameters.return_value = iter([SimpleNamespace(device='cpu')])
        model._model.generate.return_value = [[11, 12, 13, 99]]
        with patch.dict('sys.modules', {'torch': SimpleNamespace(inference_mode=nullcontext)}):
            answer = model.generate({'name': 'Test', 'category': 'Test'}, 'Câu hỏi', [], [])
        self.assertEqual(answer, 'Câu trả lời từ fixture')
        self.assertTrue(model._tokenizer.apply_chat_template.call_args.kwargs['return_dict'])
        self.assertIs(model._model.generate.call_args.kwargs['attention_mask'], attention_mask)
        self.assertIs(model._model.generate.call_args.kwargs['input_ids'], input_ids)
        self.assertEqual(model._tokenizer.decode.call_args.args[0], [99])


if __name__ == '__main__':
    unittest.main()
