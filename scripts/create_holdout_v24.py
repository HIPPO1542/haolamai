"""Freeze previously unused products/domains/questions after v2.4 development ends."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'evaluations/search_holdout_v24'
    if folder.exists():raise SystemExit('Existing holdout must never be overwritten')
    catalog=[]
    def product(store,sku,name,price,stock,attrs):
        catalog.append(dict(store_id=store,id=sku,name=name,price_vnd=price,stock=stock,attributes=attrs))
    product('motor','shared','Dung dịch làm mát động cơ',185000,5,{'dung tích':'1.25L','loại':'chăm sóc ô tô'})
    product('motor','cloth','Khăn lau kính xe',45000,0,{'chiều dài':'0.4m','loại':'chăm sóc ô tô'})
    product('music','strings','Dây đàn guitar đồng',95000,6,{'thương hiệu':'Aurora','loại':'phụ kiện nhạc cụ'})
    product('music','stand','Giá kê bản nhạc',260000,0,{'chiều dài':'1.2m','chất liệu':'nhôm'})
    product('music','radio','Bộ micro sân khấu',1890000,2,{'kết nối':'Bluetooth 5.3','màu':'đen'})
    product('music','xlr','Micro cổng XLR',790000,3,{'kết nối':'XLR','màu':'đen'})
    product('lab','shared','Ống đong thủy tinh',76000,9,{'dung tích':'250ml','chất liệu':'thủy tinh'})
    product('lab','scale','Cân bàn thí nghiệm',640000,0,{'khối lượng':'750g'})
    product('safety','mask','Mặt nạ lọc bụi',390000,2,{'tiêu chuẩn':'P2','loại':'bảo hộ lao động'})
    product('safety','glass','Kính chắn giọt bắn',85000,20,{'màu':'trong suốt','loại':'bảo hộ lao động'})
    product('aquarium','pump','Bơm tuần hoàn bể cá',470000,3,{'công suất':'0.025kW','loại':'thiết bị thủy sinh'})
    product('aquarium','lamp','Đèn thanh hồ thủy sinh',330000,0,{'công suất':'18W','chiều dài':'60cm'})
    product('cycling','tire','Lốp xe đường trường',520000,4,{'loại':'phụ kiện xe đạp','size':'700C'})
    product('cycling','spray','Bình xịt vệ sinh sên',110000,5,{'dung tích':'400ml','loại':'phụ kiện xe đạp'})
    product('sewing','spool','Suốt chỉ máy may',5000,60,{'chất liệu':'thép','loại':'vật tư may'})
    product('sewing','tape','Thước dây may',12000,0,{'chiều dài':'150cm','loại':'vật tư may'})
    product('irrigation','nozzle','Béc tưới phun sương',22000,100,{'đường kính':'8mm','loại':'vật tư tưới'})
    product('irrigation','pipe','Ống dẫn tưới',145000,8,{'chiều dài':'25m','đường kính':'8mm','loại':'vật tư tưới'})
    product('welding','rod','Que hàn thép',140000,6,{'khối lượng':'2kg','loại':'vật tư hàn'})
    product('welding','glove','Găng tay da hàn',190000,0,{'màu':'nâu','size':'XL','loại':'bảo hộ hàn'})
    product('meeting','receiver','Bộ thu trình chiếu',960000,4,{'kết nối':'Wi-Fi 5GHz','dung lượng':'64GB'})
    product('meeting','splitter','Bộ chia HDMI',245000,6,{'kết nối':'HDMI'})
    cases=[]
    def case(group,store,query,expected,filters=None,mutations=None):
        row=dict(case_id=f'H24-{len(cases)+1:03d}',category=group,store_id=store,query=query,expected_product_ids=expected)
        if filters:row['filters']=filters
        if mutations:row['mutations']=mutations
        cases.append(row)
    # New domains and names; gold is authored directly from the fixture, not retrieval.
    for item in catalog:
        case('new_domain_keyword',item['store_id'],'Xin xem '+item['name'],[item['id']])
    case('availability','motor','dung dịch làm mát còn sẵn',['shared'])
    case('availability','motor','khăn lau còn sẵn',[])
    case('availability_question','music','giá kê bản nhạc có sẵn không?',['stand'])
    case('availability','welding','găng tay hết hàng',['glove'])
    case('price_range','music','micro giá 790-1890k',['radio','xlr'])
    case('price_range','cycling','ngân sách 0,11 triệu bình xịt',['spray'])
    case('price_strict','lab','ống đong dưới 76 nghìn',[])
    case('price_inclusive','lab','ống đong ≤ 76.000đ',['shared'])
    case('price_shorthand','music','micro không quá 1tr9',['radio','xlr'])
    case('price_contradiction','meeting','bộ thu trên 1 triệu',[],{'max_price':1000000})
    case('volume','motor','dung dịch dung tích 1250ml',['shared'])
    case('length','music','giá kê chiều dài 120cm',['stand'])
    case('mass','lab','cân', ['scale'], {'attributes':{'khối lượng':'0,75kg'}})
    case('power','aquarium','bơm công suất 25W',['pump'])
    case('length','irrigation','ống dẫn chiều dài 2500cm',['pipe'])
    case('diameter','irrigation','béc tưới đường kính 0,8cm',['nozzle'])
    case('storage','meeting','bộ thu dung lượng 0,064TB',['receiver'])
    case('wireless','music','micro không dây',['radio'])
    case('wireless_spelling','music','micro blutooth',['radio'])
    case('wireless_wifi','meeting','bộ thu không dây',['receiver'])
    case('no_invented_wireless','meeting','bộ chia không dây',[])
    case('mandatory_missing_field','cycling','lốp công suất 25W',[])
    case('mandatory_color','welding','găng tay màu đen',[])
    case('mandatory_stock','welding','găng tay màu nâu size XL còn sẵn',[])
    case('multi_attribute','safety','kính',['glass'],{'in_stock':True,'attributes':{'color':'trong suốt'}})
    case('category_db','sewing','vật tư may còn sẵn',['spool'])
    case('category_db','irrigation','vật tư tưới trên 100k',['pipe'])
    case('category_db','cycling','phụ kiện xe đạp không quá 120k',['spray'])
    case('tenant','motor','ống đong thủy tinh',[])
    case('tenant','lab','dung dịch làm mát động cơ',[])
    case('tenant_sku','motor','shared',['shared'])
    case('tenant_sku','lab','shared',['shared'])
    case('unknown_tenant','absent','menu',[])
    case('sql_injection','lab',"shared'; SELECT * FROM products --",[])
    case('live_price','safety','mặt nạ dưới 300k',['mask'],mutations=[{'store_id':'safety','id':'mask','values':{'price_vnd':290000}}])
    case('live_stock','music','dây đàn còn sẵn',[],mutations=[{'store_id':'music','id':'strings','values':{'stock':0}}])
    case('live_active','aquarium','bơm tuần hoàn',[],mutations=[{'store_id':'aquarium','id':'pump','values':{'active':0}}])
    case('live_attributes','motor','dung dịch',['shared'],{'attributes':{'capacity':'2L'}},
         [{'store_id':'motor','id':'shared','values':{'attributes':{'dung tích':'2000ml'}}}])
    case('unknown_product','welding','máy ép viên dưới 5 triệu',[])
    case('dimension_mismatch','lab','ống đong',[],{'attributes':{'capacity':'250g'}})
    case('new_paraphrase','safety','đồ bảo vệ hô hấp',['mask'])
    case('new_size_syntax','cycling','lốp cỡ 700C',['tire'])
    case('new_category_paraphrase','welding','đồ bảo hộ cho thợ hàn',['glove'])
    # Verify new product names did not appear in development fixtures/source tests.
    development='\n'.join(path.read_text(encoding='utf-8-sig') for path in (ROOT/'tests').rglob('*.py'))
    assert all(item['name'] not in development for item in catalog)
    folder.mkdir(parents=True)
    (folder/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'cases.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in cases),encoding='utf-8')
    paths=[ROOT/'myai'/name for name in ('retrieval.py','normalization.py','search_lexicon.json','db.py','engine.py','grounding.py','text_index.py')]
    paths += [folder/'catalog.json',folder/'cases.jsonl']
    freeze={'created_utc':datetime.now(timezone.utc).isoformat(),'cases':len(cases),'fixture_domains':sorted({row['store_id'] for row in catalog}),
        'policy':'New authored holdout. No algorithm changes after first results; not third-party blind certification.',
        'product_names_absent_from_development_tests':True,
        'sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    (folder/'freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    print('FROZEN V24:',len(cases),'cases;',len(freeze['fixture_domains']),'new fixture domains')


if __name__=='__main__':main()
