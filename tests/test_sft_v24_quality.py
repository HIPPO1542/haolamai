import copy
import unittest
from scripts.grounded_sales_v24 import generate,verify_generated
from scripts.dataset_quality_v24 import NearQuestionIndex


def row(question):
    return {'prompt':[{'role':'user','content':'CÂU HỎI CỦA KHÁCH: '+question}],
            'completion':[{'role':'assistant','content':'Cần đối chiếu thông tin trong dữ liệu cửa hàng.'}]}


class SFTV24QualityTests(unittest.TestCase):
    def test_near_question_matches_small_word_change_but_preserves_numbers(self):
        index=NearQuestionIndex()
        index.add(row('Tôi đã nhận hàng hôm qua nhưng sản phẩm bị vỡ và tôi muốn đổi trả'),{'split':'test','line':1})
        self.assertIsNotNone(index.match(row('Tôi đã nhận hàng hôm qua nhưng sản phẩm bị vỡ và tôi muốn đổi trả nhé')))
        index.add(row('Tôi có ngân sách 200000 đồng và muốn tìm sản phẩm còn hàng để mua ngay'),{'split':'test','line':2})
        self.assertIsNone(index.match(row('Tôi có ngân sách 300000 đồng và muốn tìm sản phẩm còn hàng để mua ngay')))

    def test_generated_oracle_rejects_corrupted_answer_and_cross_tenant_facts(self):
        record,meta=next(generate(1));self.assertTrue(verify_generated(record,meta))
        corrupted=copy.deepcopy(record);corrupted['completion'][0]['content']='Giá mới là 999.000đ.'
        with self.assertRaises(AssertionError):verify_generated(corrupted,meta)
        corrupted=copy.deepcopy(record)
        corrupted['prompt'][-1]['content']=corrupted['prompt'][-1]['content'].replace('"store_id": "curated_sales_000"','"store_id": "other"',1)
        with self.assertRaises(AssertionError):verify_generated(corrupted,meta)

    def test_counterfactuals_follow_current_context_and_unavailable_comparison(self):
        tasks=set()
        for record,meta in generate(2):
            self.assertTrue(verify_generated(record,meta));tasks.add(meta['spec']['task'])
            if meta['spec'].get('empty_stock'):self.assertEqual(meta['gold_ids'],[])
        self.assertTrue({'update','update_stock','update_attrs','filter','recommend'}<=tasks)
