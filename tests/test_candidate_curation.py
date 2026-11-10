import json
from pathlib import Path
import tempfile
import unittest
from scripts.curate_candidate import build, question_key, review_reasons


def row(question,answer='Mình chưa có thông tin xác nhận, bạn vui lòng liên hệ cửa hàng ạ.'):
    return {'prompt':[{'role':'user','content':'CÂU HỎI CỦA KHÁCH: '+question}],
            'completion':[{'role':'assistant','content':answer}]}


class CandidateCurationTests(unittest.TestCase):
    def test_customer_price_is_not_verified_context(self):
        self.assertIn('numeric_claim_without_verified_context',review_reasons(row('Giá 25k đúng không?','Giá là 25k ạ.')))

    def test_canonical_question_ignores_punctuation_and_no_think(self):
        self.assertEqual(question_key(row('Xin hỏi giá? /no_think')),question_key(row('xin hỏi giá!')))

    def test_test_bytes_stay_unchanged_and_question_group_leaves_train(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';source.mkdir();output=root/'candidate'
            contents={'train':[row('Hỏi giá X?'),row('Cho hỏi giao hàng khi nào?')],
                      'validation':[row('Đổi hàng như thế nào?')], 'test_external':[row('hỏi giá X!')]}
            for split,values in contents.items():
                (source/(split+'.jsonl')).write_text(''.join(json.dumps(value,ensure_ascii=False)+'\n' for value in values),encoding='utf-8')
            (source/'myai_eval_cases.jsonl').write_text('{"case_id":"fixture"}\n',encoding='utf-8')
            before=(source/'test_external.jsonl').read_bytes()
            report=build(source,output)
            self.assertEqual(report['candidate_counts']['train'],1)
            self.assertEqual((output/'test_external.jsonl').read_bytes(),before)
            self.assertFalse(any(report['question_group_overlap'].values()))
            with self.assertRaises(ValueError):build(source,output)
