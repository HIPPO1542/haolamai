import importlib
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from myai.db import connect,initialize,add_store,add_product,create_api_key

class APITests(unittest.TestCase):
    def test_search_without_model_is_validated_and_tenant_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, 'search.sqlite3')
            conn = connect(path); initialize(conn)
            for store in ('a', 'b'):
                add_store(conn, store, store, 'test')
                add_product(conn, dict(id='same', store_id=store, name='Áo thun',
                    price_vnd=100000 if store == 'a' else 1, stock=2,
                    attributes={'size': 'L', 'màu': 'đen'}))
            key = create_api_key(conn, 'a')
            conn.close()
            with patch.dict(os.environ, {'MYAI_DB': path}):
                import myai.api as mod
                mod = importlib.reload(mod)
                with patch.object(mod.MODEL, 'verify_files', side_effect=AssertionError('Search must not load model')):
                    with TestClient(mod.app) as client:
                        self.assertEqual(client.post('/search', json={}).status_code, 401)
                        headers = {'X-API-Key': key}
                        response = client.post('/search', headers=headers, json={'query': 'áo', 'in_stock': True,
                            'min_price': 50000, 'attributes': {'size': 'L'}})
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(response.json()['count'], 1)
                        self.assertEqual(response.json()['products'][0]['store_id'], 'a')
                        for payload in ({'store_id': 'b'}, {'min_price': 2, 'max_price': 1},
                                        {'limit': 0}, {'in_stock': 'false'}, {'min_price': -1},
                                        {'attributes': {'size': {'$ne': 'L'}}}):
                            self.assertEqual(client.post('/search', headers=headers, json=payload).status_code, 422)
                        self.assertEqual(client.post('/search', headers=headers, json={'query': 'laptop dưới 200k'}).json()['count'], 0)

    def test_api_key_binds_tenant_and_missing_key_refused(self):
        with tempfile.TemporaryDirectory() as td:
            path=os.path.join(td,'tenant.sqlite3')
            conn=connect(path);initialize(conn)
            add_store(conn,'food','Cửa hàng đồ ăn','Đồ ăn')
            add_store(conn,'clothes','Cửa hàng áo','Quần áo')
            add_product(conn,dict(id='a',store_id='food',name='Rong biển',price_vnd=20000,stock=5,
                                  description='Giòn không cay'))
            add_product(conn,dict(id='a',store_id='clothes',name='Áo thun',price_vnd=150000,stock=5,
                                  description='Cotton'))
            foodkey=create_api_key(conn,'food')
            clotheskey=create_api_key(conn,'clothes')
            conn.close()
            with patch.dict(os.environ,{'MYAI_DB':path}):
                import myai.api as mod
                mod=importlib.reload(mod)
                with patch.object(mod.MODEL,'verify_files',return_value=None),\
                     patch.object(mod.MODEL,'generate',return_value='Dạ, rong biển có giá 20.000đ ạ.'):
                    with TestClient(mod.app) as client:
                        self.assertEqual(client.post('/chat',json={'question':'Rong biển giá bao nhiêu?'}).status_code,401)
                        r=client.post('/chat',json={'question':'Rong biển giá bao nhiêu?','store_id':'clothes'},
                                      headers={'X-API-Key':foodkey})
                        self.assertEqual(r.status_code,200)
                        self.assertEqual(r.json()['store_id'],'food')
                        self.assertEqual(r.json()['sources'][0]['name'],'Rong biển')
                        no_cross=client.post('/chat',json={'question':'Rong biển giá bao nhiêu?'},
                                             headers={'X-API-Key':clotheskey})
                        self.assertEqual(no_cross.status_code,200)
                        self.assertEqual(no_cross.json()['sources'],[])

if __name__=='__main__':unittest.main()
