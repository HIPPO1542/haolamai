"""Development cases; these are explicitly separate from the sealed acceptance set."""
import unittest
from myai.db import connect,initialize,add_store,add_product
from myai.retrieval import SearchFilters, search_products
from myai.text_index import BM25Index


class SearchDevelopmentTests(unittest.TestCase):
    def test_shade_alias_and_budget_constraints(self):
        conn=connect(':memory:'); initialize(conn); add_store(conn,'dev','dev','accessories')
        for sku,color in [('a','đỏ'),('b','đỏ đô')]:
            add_product(conn,dict(id=sku,store_id='dev',name='Ví da '+color,price_vnd=350000,
                                 stock=3,attributes={'màu':color,'chất liệu':'da'}))
        products=search_products(conn,'dev','ví màu đỏ đô ngân sách 350k',
                                 filters=SearchFilters(attributes={'material':'da','color':'đỏ đô'}))
        self.assertEqual([product['id'] for product in products],['b'])
        self.assertEqual(len(search_products(conn,'dev','ví không vượt quá 349k')),0)
        conn.close()

    def test_bm25_handles_empty_unknown_and_relevance(self):
        index=BM25Index([('a','green desk lamp'),('b','wooden kitchen table')])
        self.assertEqual(index.search('desk lamp')[0][0],'a')
        self.assertEqual(index.search('nonexistent'),[])
        self.assertEqual(BM25Index([]).search('lamp'),[])
