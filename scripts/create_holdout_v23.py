"""Author and freeze a new acceptance suite AFTER development tests pass.

Refuses overwrite. These examples must never be used to tune this algorithm version.
"""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    destination=ROOT/'evaluations/search_holdout_v23'
    if destination.exists():raise SystemExit('Holdout already exists; refusing to overwrite')
    catalog=[]
    def product(store,sku,name,price,stock,attributes=None,active=1):
        catalog.append(dict(store_id=store,id=sku,name=name,price_vnd=price,stock=stock,
                            attributes=attributes or {},active=active))
    product('technology','same','Pin AA Alkaline',36000,12,{'thương hiệu':'Volt','loại':'AA'})
    product('technology','headset','Tai nghe Studio BT',790000,4,{'kết nối':'Bluetooth','màu':'đen'})
    product('technology','charge','Pin sạc AA',125000,0,{'thương hiệu':'Volt'})
    product('beauty','same','Sữa rửa mặt trà xanh',125000,7,{'dung tích':'150ml','thương hiệu':'Leaf'})
    product('beauty','oil','Tinh dầu quế',95000,0,{'dung tích':'10ml'})
    product('home','kettle','Ấm đun inox',450000,2,{'dung tích':'1.8L','chất liệu':'inox'})
    product('home','water','Bình lọc nước',320000,0,{'dung tích':'2L'})
    product('pets','litter','Cát mèo đậu nành',120000,5,{'khối lượng':'6L'})
    product('pets','leash','Dây dắt nylon',90000,10,{'chất liệu':'nylon','màu':'xanh navy'})
    product('garden','seed','Hạt giống cải ngọt',25000,100,{'loại':'rau'})
    product('garden','pot','Chậu đất nung',35000,0,{'chất liệu':'đất nung'})
    product('books','geometry','Sách hình học cơ bản',85000,3,{'ngôn ngữ':'tiếng Việt'})
    product('books','pencil','Bút chì 2B',8000,0,{'độ cứng':'2B'})
    product('silk','red','Khăn lụa đỏ',310000,3,{'màu':'đỏ','chất liệu':'lụa'})
    product('silk','burgundy','Khăn lụa đỏ đô',350000,2,{'màu':'đỏ đô','chất liệu':'lụa'})
    product('silk','hidden','Khăn lụa xanh',200000,2,{'màu':'xanh'},active=0)
    cases=[]
    def case(category,store,query,expected,filters=None,mutations=None):
        row=dict(case_id=f'H23-{len(cases)+1:03d}',category=category,store_id=store,query=query,
                 expected_product_ids=expected)
        if filters:row['filters']=filters
        if mutations:row['mutations']=mutations
        cases.append(row)
    case('keyword','technology','pin AA Alkaline',['same'])
    case('keyword','beauty','sua rua mat tra xanh',['same'])
    case('keyword','home','Ấm đun inox',['kettle'])
    case('keyword','pets','Cát mèo đậu nành',['litter'])
    case('keyword','garden','Hạt giống cải ngọt',['seed'])
    case('keyword','books','Sách hình học cơ bản',['geometry'])
    case('tenant','technology','Sữa rửa mặt trà xanh',[])
    case('tenant','beauty','Pin AA Alkaline',[])
    case('tenant','unknown','menu',[])
    case('tenant','home','Cát mèo dưới 200k',[])
    case('price','technology','pin dưới 36k',[])
    case('price','technology','pin không quá 36k',['same'])
    case('price','garden','hạt giống trên 25k',[])
    case('price','garden','hạt giống tối thiểu 25k',['seed'])
    case('price','silk','khăn từ 310 đến 350k',['red','burgundy'])
    case('price','silk','khăn ngân sách 320k',['red'])
    case('price','home','ấm không vượt quá 0,45 triệu',['kettle'])
    case('price','beauty','sữa rửa mặt dưới 125.000₫',[])
    case('price','home','ấm',[],{'min_price':500000,'max_price':600000})
    case('stock','technology','Pin sạc AA còn hàng không?',['charge'])
    case('stock','technology','pin còn hàng',['same'])
    case('stock','garden','chậu hết hàng',['pot'])
    case('stock','beauty','tinh dầu',[],{'in_stock':True})
    case('stock','home','bình', ['water'], {'in_stock':False})
    case('attributes','technology','tai nghe màu đen',['headset'])
    case('attributes','silk','khăn màu đỏ đô',['burgundy'])
    case('attributes','pets','dây dắt màu xanh navy',['leash'])
    case('attributes','home','ấm',['kettle'],{'attributes':{'material':'inox','capacity':'1.8L'}})
    case('attributes','beauty','',['same'],{'attributes':{'brand':'Leaf','capacity':'150ml'}})
    case('attributes','books','bút chì',['pencil'],{'attributes':{'độ cứng':'2B'}})
    case('attributes','beauty','sữa rửa mặt',[],{'attributes':{'màu':'trắng'}})
    case('inactive','silk','khăn màu xanh',[])
    case('unsupported','technology','laptop dưới 1 triệu',[])
    case('unsupported','books',"' OR 1=1 --",[])
    case('live_update','home','ấm dưới 400k',['kettle'],mutations=[{'store_id':'home','id':'kettle','values':{'price_vnd':390000}}])
    case('live_update','beauty','sữa rửa mặt còn hàng',[],mutations=[{'store_id':'beauty','id':'same','values':{'stock':0}}])
    case('live_update','garden','hạt giống',[],mutations=[{'store_id':'garden','id':'seed','values':{'active':0}}])
    case('paraphrase','home','bình nước còn sẵn',[])
    case('paraphrase','technology','tai nghe không dây',['headset'])
    case('unit_conversion','home','ấm',['kettle'],{'attributes':{'dung tích':'1800ml'}})
    case('paraphrase','pets','đồ vệ sinh cho mèo',['litter'])
    case('range_shorthand','silk','khăn giá 300-360k',['red','burgundy'])
    destination.mkdir(parents=True)
    (destination/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'cases.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in cases),encoding='utf-8')
    paths=[ROOT/'myai/retrieval.py',ROOT/'myai/db.py',ROOT/'myai/text_index.py',destination/'catalog.json',destination/'cases.jsonl']
    freeze={'created_utc':datetime.now(timezone.utc).isoformat(),'cases':len(cases),
        'policy':'New author-created holdout after development. Do not modify algorithm after seeing results; failures remain open.',
        'sha256':{str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}}
    (destination/'freeze.json').write_text(json.dumps(freeze,indent=2),encoding='utf-8')
    print('FROZEN',len(cases),'cases')


if __name__=='__main__':main()
