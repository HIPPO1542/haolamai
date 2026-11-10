"""Development fixtures; deliberately distinct from the new v2.4 holdout."""
import unittest
from myai.db import connect,initialize,add_store,add_product
from myai.normalization import measurement,equivalent_value
from myai.retrieval import SearchFilters,search_products,price_constraints


class NormalizationTests(unittest.TestCase):
    def test_measurement_dimensions_and_vietnamese_decimal(self):
        for actual,requested in [('1.25L','1250ml'),('0,75 kg','750g'),('150cm','1.5m'),
                                 ('2 kW','2000W'),('1GB','1000MB'),('1.800 ml','1,8 lít')]:
            self.assertTrue(equivalent_value(actual,requested),(actual,requested))
        self.assertFalse(equivalent_value('500g','500ml'))
        self.assertFalse(equivalent_value('1GiB','1GB'))
        self.assertIsNone(measurement('invalid'))

    def test_price_range_and_shorthand(self):
        cases={'250–410k':(250000,410000),'giá 1tr2-2tr125':(1200000,2125000),
               'không quá 1.500.000đ':(None,1500000),'≤ 90 ngàn':(None,90000),
               'tối thiểu 0,25 triệu':(250000,None)}
        for query,expected in cases.items():self.assertEqual(price_constraints(query)[:2],expected,query)


class SearchV24DevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.conn=connect(':memory:');initialize(self.conn)
        for store in ('dev','other'):add_store(self.conn,store,store,'mixed')
        for sku,name,price,stock,attrs in [
            ('mouse','Chuột văn phòng',230000,5,{'kết nối':'Bluetooth 5.2','màu':'đen'}),
            ('usb','Chuột chơi game',310000,4,{'kết nối':'USB','màu':'đỏ'}),
            ('unknown','Chuột cơ bản',180000,5,{}),
            ('bottle','Bình thể thao',190000,0,{'dung tích':'0.75L'}),
            ('cat','Khay vệ sinh mèo',275000,3,{'loại':'khay vệ sinh mèo'}),
            ('tape','Băng keo giấy',25000,10,{'chiều dài':'5m'})]:
            add_product(self.conn,dict(id=sku,store_id='dev',name=name,price_vnd=price,stock=stock,attributes=attrs))
        add_product(self.conn,dict(id='mouse',store_id='other',name='Chuột văn phòng',price_vnd=1,stock=99,attributes={'kết nối':'Bluetooth'}))

    def tearDown(self):self.conn.close()
    def ids(self,query,filters=None):return [p['id'] for p in search_products(self.conn,'dev',query,filters=filters)]

    def test_wireless_requires_catalog_evidence(self):
        self.assertEqual(self.ids('chuột không dây'),['mouse'])
        self.assertEqual(self.ids('chuột bluetooh'),['mouse'])
        self.assertEqual(self.ids('chuột ko dây màu đen'),['mouse'])

    def test_available_question_and_mandatory_stock(self):
        self.assertEqual(self.ids('bình còn sẵn'),[])
        self.assertEqual(self.ids('bình còn sẵn không?'),['bottle'])
        self.assertEqual(self.ids('bình',SearchFilters(in_stock=True)),[])

    def test_measurement_constraints_and_category(self):
        self.assertEqual(self.ids('bình',SearchFilters(attributes={'capacity':'750ml'})),['bottle'])
        self.assertEqual(self.ids('băng keo',SearchFilters(attributes={'chiều dài':'500cm'})),['tape'])
        self.assertEqual(self.ids('đồ vệ sinh cho mèo còn sẵn dưới 300k'),['cat'])
        self.assertEqual(self.ids('đồ vệ sinh cho mèo',SearchFilters(in_stock=False)),[])
        self.assertEqual(self.ids('Vui lòng tìm giúp tôi bình dung tích 750ml'),['bottle'])
        self.assertEqual(self.ids('băng keo chiều dài 500cm'),['tape'])
        self.assertEqual(self.ids('chuột dung tích 750ml'),[])

    def test_mandatory_negation_and_unknown_attributes(self):
        self.assertNotIn('usb',self.ids('chuột không màu đỏ'))
        self.assertNotIn('unknown',self.ids('chuột không màu đỏ'))
        self.assertEqual(self.ids('chuột không Bluetooth'),[])
        self.assertEqual(self.ids('chuột',SearchFilters(attributes={'capacity':'1L'})),[])

    def test_constraints_intersect_and_empty_ranges(self):
        self.assertEqual(self.ids('chuột giá 200-250k'),['mouse'])
        self.assertEqual(self.ids('chuột trên 250k',SearchFilters(max_price=250000)),[])
