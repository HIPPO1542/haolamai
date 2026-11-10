"""Local CLI administration. Never expose tenant administration to untrusted web clients."""
import argparse
import csv
import json
from myai.db import (connect,initialize,add_store,add_product,add_knowledge,
                    create_api_key,revoke_api_key)

def main():
    parser=argparse.ArgumentParser(description='MyAI tenant and catalog administration')
    parser.add_argument('--db',default='data/myai.sqlite3')
    sub=parser.add_subparsers(dest='operation',required=True)
    p=sub.add_parser('create-store')
    p.add_argument('id');p.add_argument('name');p.add_argument('category')
    p=sub.add_parser('new-key');p.add_argument('store_id')
    p=sub.add_parser('revoke-key');p.add_argument('key')
    p=sub.add_parser('import-products')
    p.add_argument('store_id');p.add_argument('csv_file')
    p=sub.add_parser('set-policy')
    p.add_argument('store_id');p.add_argument('doc_id');p.add_argument('title');p.add_argument('content')
    args=parser.parse_args()
    conn=connect(args.db);initialize(conn)
    try:
        if args.operation=='create-store':
            add_store(conn,args.id,args.name,args.category)
            print('Created store:',args.id)
        elif args.operation=='new-key':
            print('SAVE THIS KEY NOW; shown only once:\n'+create_api_key(conn,args.store_id))
        elif args.operation=='revoke-key':
            revoke_api_key(conn,args.key);print('Key revoked')
        elif args.operation=='import-products':
            with open(args.csv_file,encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            required={'id','name','price_vnd','stock'}
            if not rows or not required.issubset(rows[0]):
                raise ValueError('CSV requires id,name,price_vnd,stock columns')
            for row in rows:
                add_product(conn,dict(id=row['id'],store_id=args.store_id,name=row['name'],
                    price_vnd=int(row['price_vnd']),stock=int(row['stock']),
                    description=row.get('description',''),
                    attributes=json.loads(row.get('attributes_json') or '{}'),
                    active=int(row.get('active','1'))))
            print('Imported rows:',len(rows))
        elif args.operation=='set-policy':
            add_knowledge(conn,args.doc_id,args.store_id,args.title,args.content)
            print('Policy saved')
    finally:conn.close()

if __name__=='__main__':main()
