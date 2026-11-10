"""Safely imports sample catalogs and policies into the user's existing MyAI v0.3 project.
No proprietary third-party datasets, model files, or adapter files are altered.
"""
import argparse, csv, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def csv_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--project-root',default='.',help='Root folder of MyAI_v0_3_Windows')
    parser.add_argument('--apply',action='store_true',help='Actually write sample data; without flag show preview only')
    parser.add_argument('--allow-overwrite',action='store_true',help='Allow upserting stores that already exist')
    args=parser.parse_args()
    project=Path(args.project_root).resolve()
    if not (project/'myai/db.py').is_file():raise SystemExit('Invalid --project-root; expected myai/db.py')
    store_rows=csv_rows(ROOT/'01_database/stores.csv')
    rows_by_store={
      'food01':csv_rows(ROOT/'01_database/snacks_products.csv'),
      'fashion01':csv_rows(ROOT/'01_database/fashion_products.csv')}
    policy_rows=[]
    for line in (ROOT/'02_policies/policies.jsonl').read_text(encoding='utf-8').splitlines():
        if line.strip():policy_rows.append(json.loads(line))
    print('Target:',project/'data/myai.sqlite3')
    print('Stores:',[x['id'] for x in store_rows], '| Product rows:',sum(map(len,rows_by_store.values())), '| Policies:',len(policy_rows))
    if not args.apply:
        print('DRY RUN only. Add --apply to import; existing stores are protected unless --allow-overwrite')
        return
    sys.path.insert(0,str(project))
    from myai.db import connect,initialize,get_store,add_store,add_product,add_knowledge
    dbpath=project/'data/myai.sqlite3'
    conn=connect(dbpath)
    try:
        initialize(conn)
        existing=[row['id'] for row in store_rows if get_store(conn,row['id'])]
        if existing and not args.allow_overwrite:
            raise RuntimeError('Existing store IDs found: '+', '.join(existing)+'. Aborted to avoid overwriting. Use --allow-overwrite only if intentional.')
        for s in store_rows:
            add_store(conn,s['id'],s['name'],s['category'])
            for row in rows_by_store[s['id']]:
                add_product(conn,{'store_id':s['id'],'id':row['id'],'name':row['name'],
                  'price_vnd':int(row['price_vnd']),'stock':int(row['stock']),
                  'description':row['description'],'attributes':json.loads(row['attributes_json']),
                  'active':int(row['active'])})
        for p in policy_rows:
            add_knowledge(conn,p['id'],p['store_id'],p['title'],p['content'])
        print('SUCCESS | Sample stores/products/policies imported. No API keys generated.')
        print('To create an API key: py -3.11 -m scripts.store_admin new-key food01')
    finally:conn.close()

if __name__=='__main__':main()
