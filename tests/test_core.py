import tempfile
import unittest
from pathlib import Path
from myai.db import (connect,initialize,add_store,add_product,create_api_key,
                     resolve_api_key,revoke_api_key,get_products)
from myai.retrieval import retrieve,maximum_price,wanted_size,wanted_color
from myai.engine import SalesAssistant,currency_values,LocalQwen

class EchoGenerator:
    """Inject test seam; production never loads this class or has a demo mode."""
    def __init__(self, answer):self.answer=answer;self.calls=0
    def generate(self, store, question, products, docs):
        self.calls+=1
        return self.answer

class MyAITests(unittest.TestCase):
    def setUp(self):
        self.conn=connect(':memory:');initialize(self.conn)
        add_store(self.conn,'food','Ăn vặt','Đồ ăn')
        add_store(self.conn,'fashion','Áo đẹp','Quần áo')
        add_product(self.conn,{'id':'p1','store_id':'food','name':'Rong biển cháy tỏi',
            'price_vnd':20000,'stock':12,'description':'Giòn, không cay.'})
        add_product(self.conn,{'id':'p2','store_id':'food','name':'Bánh tráng trộn',
            'price_vnd':25000,'stock':8,'description':'Vị cay nhẹ.'})
        add_product(self.conn,{'id':'p1','store_id':'fashion','name':'Áo thun cotton',
            'price_vnd':150000,'stock':4,'description':'Vải cotton.',
            'attributes':{'màu':['đen','trắng'],'size':['M','L','XL']}})
    def tearDown(self):self.conn.close()

    def test_tenant_key_isolation(self):
        foodkey=create_api_key(self.conn,'food')
        fashionkey=create_api_key(self.conn,'fashion')
        self.assertEqual(resolve_api_key(self.conn,foodkey)['id'],'food')
        self.assertEqual(resolve_api_key(self.conn,fashionkey)['id'],'fashion')
        self.assertIsNone(resolve_api_key(self.conn,'myai_fake'))
        revoke_api_key(self.conn,foodkey)
        self.assertIsNone(resolve_api_key(self.conn,foodkey))

    def test_products_scoped_in_db(self):
        self.assertEqual(get_products(self.conn,'food')[0]['name'],'Bánh tráng trộn')
        self.assertEqual(get_products(self.conn,'fashion')[0]['name'],'Áo thun cotton')

    def test_price_filter(self):
        p,_=retrieve(self.conn,'food','Món không cay dưới 30k?')
        self.assertEqual([x['name'] for x in p],['Rong biển cháy tỏi'])
        self.assertEqual(maximum_price('không quá 200 nghìn'),200000)

    def test_size_color(self):
        self.assertEqual(wanted_size('Có áo size XL không?'),'XL')
        self.assertEqual(wanted_color('Có áo màu đen không?'),'den')
        self.assertEqual([x['name'] for x in retrieve(self.conn,'fashion','Áo thun size XL màu đen')[0]],['Áo thun cotton'])
        self.assertFalse(retrieve(self.conn,'food','Áo thun size XL màu đen')[0])

    def test_no_cross_store_lookup(self):
        p,_=retrieve(self.conn,'food','Áo thun cotton giá bao nhiêu?')
        self.assertEqual(p,[])

    def test_no_source_never_calls_model(self):
        gen=EchoGenerator('Trả lời bịa')
        result=SalesAssistant(self.conn,gen).respond('food','Áo thun cotton giá bao nhiêu?')
        self.assertEqual(gen.calls,0)
        self.assertFalse(result['generated_by_ai'])

    def test_model_is_called_for_existing_product(self):
        gen=EchoGenerator('Dạ rong biển cháy tỏi có giá 20.000đ ạ.')
        result=SalesAssistant(self.conn,gen).respond('food','Rong biển cháy tỏi bao nhiêu tiền?')
        self.assertEqual(gen.calls,1)
        self.assertTrue(result['generated_by_ai'])

    def test_reject_wrong_price(self):
        gen=EchoGenerator('Giá rong biển cháy tỏi là 99.000đ ạ.')
        result=SalesAssistant(self.conn,gen).respond('food','Rong biển cháy tỏi bao nhiêu tiền?')
        self.assertEqual(result['reason'],'failed_basic_grounding_check')
        self.assertIn('20.000đ',result['answer'])
        self.assertEqual(currency_values('99.000đ và 35k'),[99000,35000])
        self.assertEqual(currency_values('99.000₫ và 35 nghìn'), [99000, 35000])

    def test_malformed_model_price_uses_verified_facts(self):
        gen = EchoGenerator('Giá rong biển là 1.2.3k.')
        result = SalesAssistant(self.conn, gen).respond('food', 'Rong biển giá bao nhiêu?')
        self.assertEqual(result['reason'], 'failed_basic_grounding_check')
        self.assertIn('20.000đ', result['answer'])

    def test_unexecuted_actions_and_wrong_stock_are_rejected(self):
        for answer in ('Em đã đặt hàng thành công.', 'Em đã hoàn tiền cho bạn.',
                       'Em đã đặt lịch cho bạn.', 'Em đang chuyển bạn đến nhân viên.'):
            result=SalesAssistant(self.conn,EchoGenerator(answer)).respond('food','Rong biển giá bao nhiêu?')
            self.assertEqual(result['reason'],'unverified_backend_action',answer)
        result=SalesAssistant(self.conn,EchoGenerator('Rong biển còn 99 sản phẩm.')).respond('food','Rong biển còn hàng không?')
        self.assertEqual(result['reason'],'unsupported_stock_claim')

    def test_database_update_no_retraining(self):
        gen=EchoGenerator('Giá rong biển cháy tỏi là 30.000đ ạ.')
        self.conn.execute('UPDATE products SET price_vnd=30000 WHERE store_id=? AND id=?',('food','p1'))
        self.conn.commit()
        result=SalesAssistant(self.conn,gen).respond('food','Rong biển cháy tỏi bao nhiêu tiền?')
        self.assertTrue(result['generated_by_ai'])
        self.assertEqual(result['sources'][0]['price_vnd'],30000)

    def test_verify_files_requires_adapter(self):
        with tempfile.TemporaryDirectory() as d:
            model=Path(d)/'model';model.mkdir();(model/'config.json').write_text('{}')
            (model/'weights.safetensors').write_bytes(b'not-real-weights')
            with self.assertRaises(RuntimeError):LocalQwen(model,Path(d)/'missing').verify_files()

    def test_no_generator_is_rejected(self):
        with self.assertRaises(ValueError):SalesAssistant(self.conn,None)

if __name__=='__main__':unittest.main()
