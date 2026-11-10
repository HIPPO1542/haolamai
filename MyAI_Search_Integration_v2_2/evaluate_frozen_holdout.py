"""Evaluate a frozen new catalog/query set exactly once; never tune against it."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from myai.db import connect, initialize, add_store, add_product
from myai.retrieval import SearchFilters,search_products


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--suite',default='evaluations/search_holdout_v23')
    parser.add_argument('--output',required=True)
    parser.add_argument('--regression',action='store_true',help='Old suite used for development; verify test bytes, not old algorithm hashes')
    args=parser.parse_args()
    suite=ROOT/args.suite;output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs') or output.exists():parser.error('Use a new result path under outputs')
    freeze=json.loads((suite/'freeze.json').read_text(encoding='utf-8'))
    for relative,digest in freeze['sha256'].items():
        if args.regression and not (ROOT/relative).is_relative_to(suite):continue
        if sha(ROOT/relative)!=digest:raise RuntimeError('Frozen algorithm or suite changed: '+relative)
    catalog=json.loads((suite/'catalog.json').read_text(encoding='utf-8'))
    cases=[json.loads(line) for line in (suite/'cases.jsonl').read_text(encoding='utf-8').splitlines()]
    results=[]
    for case in cases:
        conn=connect(':memory:')
        try:
            initialize(conn)
            for store in sorted({product['store_id'] for product in catalog}):add_store(conn,store,store,'new heldout fixture')
            for product in catalog:add_product(conn,product)
            for mutation in case.get('mutations',[]):
                changed=next(dict(product,**mutation['values']) for product in catalog
                             if product['store_id']==mutation['store_id'] and product['id']==mutation['id'])
                add_product(conn,changed)
            products=search_products(conn,case['store_id'],case['query'],filters=SearchFilters(**case.get('filters',{})))
            ids=[product['id'] for product in products]
            passed=set(ids)==set(case['expected_product_ids']) and all(product['store_id']==case['store_id'] for product in products)
            results.append({'case_id':case['case_id'],'passed':passed,'actual_product_ids':ids,
                            'expected_product_ids':case['expected_product_ids'],'category':case['category']})
        finally:conn.close()
    report={'scope':('Regression of former holdout; used for algorithm fixes, not independent acceptance.' if args.regression
                     else 'New authored acceptance cases; no algorithm edits after freeze or after first results.'),
        'freeze_sha256':sha(suite/'freeze.json'),'total':len(results),'passed':sum(row['passed'] for row in results),
        'cases':results,'limitations':['Author-created suite, not an external blind human acceptance study.',
            'No test examples used for SFT.']}
    with output.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print('REGRESSION' if args.regression else 'FROZEN HOLDOUT',report['passed'],'/',report['total'])
    for row in results:
        if not row['passed']:print('FAIL',row['case_id'],row['category'],row['actual_product_ids'],row['expected_product_ids'])
    return 0 if report['passed']==report['total'] else 2


if __name__=='__main__':raise SystemExit(main())
