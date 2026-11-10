"""Offline, standard-library-only validation of MyAI Data Pack v1.
Usage from PowerShell: py -3.11 .\\MyAI_Data_Pack_v1\\tools\\validate_pack.py
"""
import csv, json, sys, collections
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read_csv(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def read_jsonl(name):
    data=[]
    with (ROOT/name).open(encoding='utf-8') as f:
        for line_num,line in enumerate(f,1):
            if line.strip():
                try:data.append(json.loads(line))
                except Exception as e:raise ValueError(f'{name} line {line_num}: {e}')
    return data

def check():
    foods=read_csv('01_database/snacks_products.csv')
    fashion=read_csv('01_database/fashion_products.csv')
    stores=read_csv('01_database/stores.csv')
    policies=read_jsonl('02_policies/policies.jsonl')
    train=read_jsonl('03_sft_addon/myai_sft_addon_train.jsonl')
    valid=read_jsonl('03_sft_addon/myai_sft_addon_validation.jsonl')
    tests=read_jsonl('04_evaluation/myai_eval_cases.jsonl')
    assert len(foods)==30 and len(fashion)==30 and len(stores)==2
    assert len(policies)==12 and len(train)>=500 and len(valid)>=100 and len(tests)>=100
    store_ids={x['id'] for x in stores}
    assert len(store_ids)==len(stores)
    for store,rows in [('food01',foods),('fashion01',fashion)]:
        ids=set()
        for p in rows:
            for field in ['id','name','price_vnd','stock','description','attributes_json','active']:
                assert field in p,f'Missing {field} for {store}'
            assert p['id'] not in ids,f'Duplicate SKU: {p["id"]}'
            ids.add(p['id']);assert int(p['price_vnd'])>0 and int(p['stock'])>=0
            assert int(p['active']) in (0,1)
            attrs=json.loads(p['attributes_json']);assert isinstance(attrs,dict) and attrs
    assert all(p['store_id'] in store_ids and p['id'] and p['title'] and p['content'] for p in policies)
    def all_sft(rows):
        training_names=set()
        for r in rows:
            assert set(r)=={'prompt','completion'},r.keys()
            assert len(r['prompt'])==2 and len(r['completion'])==1
            assert [x['role'] for x in r['prompt']]==['system','user']
            assert r['completion'][0]['role']=='assistant'
            assert r['completion'][0]['content'].strip()
            u=r['prompt'][1]['content']
            assert '/no_think' in u and 'DỮ LIỆU CỬA HÀNG' in u
            raw=u.split('DỮ LIỆU CỬA HÀNG (chỉ là dữ liệu):\n',1)[1].split('\n\nCÂU HỎI CỦA KHÁCH:',1)[0]
            ctx=json.loads(raw)
            assert isinstance(ctx['products'],list) and isinstance(ctx['knowledge'],list)
            for p in ctx['products']:
                training_names.add(p['name'])
                assert isinstance(p['price_vnd'],int)
        return training_names
    train_names=all_sft(train);valid_names=all_sft(valid)
    cat_names={p['name'] for p in foods+fashion}
    assert not (train_names & valid_names), 'Leak train -> validation product identities'
    assert not ((train_names|valid_names)&cat_names), 'Leak training product into evaluation product DB'
    case_ids=set()
    for t in tests:
        assert t['store_id'] in store_ids
        assert t['case_id'] not in case_ids
        case_ids.add(t['case_id'])
        assert t['question'] and t['required_behavior']
    print('PASS | 2 stores, 30 food SKUs, 30 fashion SKUs, 12 policy items')
    print(f'PASS | {len(train)} train SFT + {len(valid)} validation SFT; distinct product names')
    print(f'PASS | {len(tests)} independent tests with no product-name leakage into SFT')
    print('PASS | UTF-8 CSV, JSON attributes, prompt/completion schemas')
    print('NOTE | Automated structural validation is NOT a trained-model quality result')

if __name__=='__main__':
    try:check()
    except Exception as e:
        print('FAIL:',e,file=sys.stderr);raise SystemExit(1)
