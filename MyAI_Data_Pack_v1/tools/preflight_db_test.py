"""Smoke-test real v0.3 SQLite isolation and catalog mutations, without loading Qwen.
Run: py -3.11 .\\MyAI_Data_Pack_v1\\tools\\preflight_db_test.py --project-root .
"""
import argparse, csv, json, tempfile, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def readrows(path):
    with (ROOT/path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    p=argparse.ArgumentParser();p.add_argument('--project-root',default='.')
    project=Path(p.parse_args().project_root).resolve()
    if not (project/'myai/db.py').is_file():raise SystemExit('Bad --project-root')
    sys.path.insert(0,str(project))
    from myai.db import connect,initialize,add_store,add_product,get_products,get_store,add_knowledge,get_knowledge
    from myai.retrieval import retrieve
    foods=readrows('01_database/snacks_products.csv');fashion=readrows('01_database/fashion_products.csv')
    with tempfile.TemporaryDirectory(prefix='myai_preflight_') as d:
        conn=connect(Path(d)/'scratch.sqlite3');initialize(conn)
        for store,category,rows in [('food01','Đồ ăn',foods),('fashion01','Quần áo',fashion)]:
            add_store(conn,store,'Test only',category)
            for p in rows:
                add_product(conn,{'store_id':store,'id':p['id'],'name':p['name'],
                  'price_vnd':int(p['price_vnd']),'stock':int(p['stock']),
                  'description':p['description'],'attributes':json.loads(p['attributes_json']),
                  'active':int(p['active'])})
        assert len(get_products(conn,'food01'))==30 and len(get_products(conn,'fashion01'))==30
        assert not any(p['id'].startswith('A') for p in get_products(conn,'food01'))
        assert not any(p['id'].startswith('F') for p in get_products(conn,'fashion01'))
        assert get_store(conn,'food01')['category']=='Đồ ăn'
        # Change prices/stocks without a model retrain.
        conn.execute("UPDATE products SET price_vnd=27000 WHERE store_id='food01' AND id='F009'")
        conn.execute("UPDATE products SET stock=0 WHERE store_id='fashion01' AND id='A005'")
        conn.commit()
        f={p['id']:p for p in get_products(conn,'food01')};a={p['id']:p for p in get_products(conn,'fashion01')}
        assert f['F009']['price_vnd']==27000 and a['A005']['stock']==0
        # DB-layer isolation: these product IDs cannot leak into the other tenant.
        assert 'F009' not in a and 'A005' not in f
        # Sample policies stay scoped too.
        policies=[json.loads(x) for x in (ROOT/'02_policies/policies.jsonl').read_text(encoding='utf-8').splitlines() if x]
        for doc in policies:add_knowledge(conn,doc['id'],doc['store_id'],doc['title'],doc['content'])
        assert len(get_knowledge(conn,'food01'))==6 and len(get_knowledge(conn,'fashion01'))==6
        print('PASS | Sample DB 60 SKUs, 12 policies, tenant separation, price+stock updates')
        # This is intentionally informational: lexical retrieval may not satisfy all heldout questions.
        q_food=retrieve(conn,'food01','Rong biển cháy tỏi giá bao nhiêu?')[0]
        q_fash=retrieve(conn,'fashion01','Áo polo piqué kem size M còn không?')[0]
        print('INFO | retrieval food source ids:',[p['id'] for p in q_food])
        print('INFO | retrieval fashion source ids:',[p['id'] for p in q_fash])
        print('NOTE | No Qwen inference or fine-tuning was run. Real model tests still pending.')
        conn.close()

if __name__=='__main__':main()
