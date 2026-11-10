import unittest
from myai.db import connect, initialize, add_store, add_product
from myai.retrieval import SearchFilters, search_products, price_constraints


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.conn = connect(':memory:')
        initialize(self.conn)
        for store in ('a', 'b'):
            add_store(self.conn, store, store, 'multi-sector')
        for store, sku, name, price, stock, attrs in [
            ('a', 'black', 'Áo thun cotton', 150000, 4, {'màu': 'đen', 'size': ['M', 'L'], 'chất liệu': 'cotton'}),
            ('a', 'white', 'Áo thun trắng', 200000, 0, {'màu': 'trắng', 'size': 'L'}),
            ('a', 'cup', 'Cốc thủy tinh', 50000, 5, {'dung tích': '300ml'}),
            ('b', 'black', 'Áo thun cotton', 10000, 10, {'màu': 'đen', 'size': 'XL'})]:
            add_product(self.conn, dict(id=sku, store_id=store, name=name, price_vnd=price, stock=stock, attributes=attrs))

    def tearDown(self):
        self.conn.close()

    def ids(self, query, **kwargs):
        return [product['id'] for product in search_products(self.conn, 'a', query, **kwargs)]

    def test_unknown_keywords_do_not_fall_back_to_filters_or_generic_words(self):
        for question in ('Laptop dưới 200k', 'Shop có bán sushi không?', 'Giày màu đen size L', 'Không có XYZ dưới 200k'):
            self.assertEqual(self.ids(question), [], question)

    def test_prices_boundaries_and_notation(self):
        self.assertEqual(self.ids('áo dưới 200.000đ'), ['black'])
        self.assertEqual(self.ids('áo dưới 200.000₫'), ['black'])
        self.assertEqual(self.ids('áo không quá 200 nghìn'), ['black', 'white'])
        self.assertEqual(self.ids('áo trên 150k'), ['white'])
        self.assertEqual(self.ids('áo từ 150 đến 200k'), ['black', 'white'])
        self.assertEqual(self.ids('áo từ 0,15 triệu đến 0.2 triệu'), ['black', 'white'])
        self.assertEqual(self.ids('áo trên 200k dưới 150k'), [])
        self.assertEqual(self.ids('áo dưới 1.2.3k'), [])
        self.assertEqual(price_constraints('tối đa 1.500.000 VND')[:2], (None, 1500000))

    def test_stock_question_is_distinct_from_filter(self):
        self.assertEqual(self.ids('Áo thun trắng còn hàng không?'), ['white'])
        self.assertEqual(self.ids('Áo thun còn hàng'), ['black'])
        self.assertEqual(self.ids('Áo thun hết hàng'), ['white'])
        self.assertEqual(self.ids('Áo thun không còn hàng'), ['white'])
        self.assertEqual(self.ids('áo', filters=SearchFilters(in_stock=False)), ['white'])

    def test_attributes_and_shop_scope(self):
        self.assertEqual(self.ids('ao thun size L mau den'), ['black'])
        self.assertEqual(self.ids('áo size XL màu đen'), [])
        self.assertEqual(self.ids('', filters=SearchFilters(attributes={'CHẤT LIỆU': 'Cotton'})), ['black'])
        self.assertEqual(self.ids('cốc', filters=SearchFilters(attributes={'dung tích': '300ml'})), ['cup'])
        self.assertEqual(self.ids('cốc', filters=SearchFilters(attributes={'màu': 'đen'})), [])

    def test_ambiguous_vietnamese_words_preserve_product_identity(self):
        add_product(self.conn, dict(id='skirt', store_id='a', name='Váy trắng', price_vnd=1, stock=1))
        self.assertEqual(self.ids('váy trắng'), ['skirt'])
        self.assertEqual(self.ids('áo thun trắng'), ['white'])
        add_product(self.conn, dict(id='garlic', store_id='a', name='Tỏi', price_vnd=1, stock=1))
        self.assertEqual(self.ids('tỏi'), ['garlic'])
        self.assertEqual(self.ids('Tôi muốn áo thun trắng'), ['white'])

    def test_current_data_and_inactive(self):
        self.conn.execute("UPDATE products SET active=0 WHERE store_id='a' AND id='black'")
        self.assertEqual(self.ids('áo màu đen'), [])
        self.assertEqual(self.ids("' OR 1=1 --"), [])
        self.assertEqual(search_products(self.conn, 'missing', 'menu'), [])

    def test_sku_with_separators(self):
        add_product(self.conn, dict(id='SKU-ABC-123', store_id='a', name='Hàng mới', price_vnd=1, stock=1))
        self.assertEqual(self.ids('SKU-ABC-123'), ['SKU-ABC-123'])

    def test_catalog_beyond_old_candidate_limit(self):
        for index in range(2001):
            self.conn.execute('INSERT INTO products(id,store_id,name,price_vnd) VALUES(?,?,?,?)',
                              (str(index), 'a', 'AAA '+str(index), 1))
        add_product(self.conn, dict(id='last', store_id='a', name='ZZZ độc đáo', price_vnd=1, stock=1))
        self.assertEqual(self.ids('ZZZ độc đáo'), ['last'])

    def test_invalid_filters(self):
        for kwargs in ({'min_price': -1}, {'min_price': 10, 'max_price': 1}, {'min_price': True}, {'in_stock': 'false'}):
            with self.assertRaises(ValueError):
                SearchFilters(**kwargs)


if __name__ == '__main__':
    unittest.main()
