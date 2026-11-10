import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import prepare_v2 as p
from synthetic_cases import generate_grounded_examples

class TestV2(unittest.TestCase):
    def test_strict_budget_does_not_recommend_equal_price(self):
        checked = 0
        for row in generate_grounded_examples(42, 1500, p.SYSTEM):
            user = p.get_user(row)
            if 'CÂU HỎI CỦA KHÁCH: Shop có món nào dưới ' not in user:
                continue
            checked += 1
            context_text = user.split('(chỉ là dữ liệu): ', 1)[1]
            facts, end = json.JSONDecoder().raw_decode(context_text)
            question = context_text[end:]
            import re
            budget = int(re.search(r'dưới ([\d.]+)đ', question).group(1).replace('.', ''))
            answer = p.get_answer(row)
            for product in facts['products']:
                if product['name'] in answer:
                    self.assertLess(product['price_vnd'], budget)
        self.assertGreater(checked, 0)
    def test_grounded_synthetic(self):
        rows=generate_grounded_examples(12,260,p.SYSTEM)
        self.assertEqual(len(rows),260)
        for r in rows:
            status,why=p.analyze(r,'synthetic')
            self.assertEqual((status,why),('accept','ok'))
            self.assertIn('DỮ LIỆU CỬA HÀNG',p.get_user(r))
        self.assertEqual(len({p.topic_fp(r) for r in rows}),260)
    def test_raw_saas(self):
        raw={'language':'vi','messages':[{'role':'system','content':'Bạn là shop quần áo. Giá 120.000đ.'},{'role':'user','content':'Áo thun bao nhiêu tiền?'},{'role':'assistant','content':'Áo thun có giá 120.000đ ạ.'}]}
        r,err=p.standardize(raw,'saas');self.assertIsNone(err)
        self.assertEqual(p.analyze(r,'saas'),('accept','ok'))
    def test_quarantine_action(self):
        raw={'language':'vi','messages':[{'role':'user','content':'Đặt lịch mai giúp mình nhé.'},{'role':'assistant','content':'Đã đặt thành công, mã ABC.'}]}
        r,err=p.standardize(raw,'saas');self.assertIsNone(err)
        self.assertEqual(p.analyze(r,'saas')[0],'review')
    def test_personal_data(self):
        rec={'prompt':[{'role':'system','content':p.SYSTEM},{'role':'user','content':'Gọi tôi theo số 0912345678.'}],
            'completion':[{'role':'assistant','content':'Đã nhận thông tin của bạn ạ.'}]}
        self.assertEqual(p.analyze(rec,'empath')[1],'possible_personal_data')
    def test_topic_mismatch(self):
        r={'prompt':[{'role':'system','content':p.SYSTEM},{'role':'user','content':'Tôi nhận áo bị sứt chỉ muốn đổi hàng.'}],
            'completion':[{'role':'assistant','content':'Vấn đề thanh toán của anh chị đang được xử lý.'}]}
        self.assertEqual(p.analyze(r,'empath')[1],'likely_topic_mismatch')
    def test_addon_schema(self):
        a={'prompt':[{'role':'system','content':'old system'},{'role':'user','content':'Còn sản phẩm X không?'}],
           'completion':[{'role':'assistant','content':'Mình chưa có dữ liệu xác nhận tồn kho ạ.'}]}
        r,err=p.standardize(a,'addon');self.assertIsNone(err)
        self.assertIn('MyAI',r['prompt'][0]['content'])
        self.assertNotIn('old system',str(r))

if __name__=='__main__':unittest.main()
