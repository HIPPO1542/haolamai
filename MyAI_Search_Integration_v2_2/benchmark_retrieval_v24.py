"""Compare the current exact-filter search with the preserved v2.3 baseline."""
import argparse
import importlib.util
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from myai.db import connect,initialize,add_store,add_product
from myai.retrieval import search_products


def fixture(catalog,case):
    conn=connect(':memory:');initialize(conn)
    for store in sorted({row['store_id'] for row in catalog}):add_store(conn,store,store,'benchmark fixture')
    for original in catalog:
        row=dict(original)
        for mutation in case.get('mutations',[]):
            if mutation['store_id']==row['store_id'] and mutation['id']==row['id']:row.update(mutation['values'])
        add_product(conn,row)
    return conn


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs/v2_4') or output.exists():parser.error('Use a new v2.4 report path')
    baseline=ROOT/'outputs/v2_4/baseline/source_backup/myai/retrieval.py'
    spec=importlib.util.spec_from_file_location('myai._v23_search_benchmark',baseline)
    old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
    suite=ROOT/'evaluations/search_holdout_v23'
    catalog=json.loads((suite/'catalog.json').read_text(encoding='utf-8'))
    cases=[json.loads(line) for line in (suite/'cases.jsonl').read_text(encoding='utf-8').splitlines()]
    rows=[]
    for version,function in [('v23',old.search_products),('v24',search_products)]:
        passed=0;durations=[]
        for case in cases:
            conn=fixture(catalog,case)
            filters=function.__globals__['SearchFilters'](**case.get('filters',{}))
            for iteration in range(6):
                start=time.perf_counter();products=function(conn,case['store_id'],case['query'],filters=filters)
                elapsed=(time.perf_counter()-start)*1000
                if iteration:durations.append(elapsed)
            passed+=set(p['id'] for p in products)==set(case['expected_product_ids'])
            conn.close()
        rows.append({'version':version,'regression_passed':passed,'regression_total':len(cases),
            'calls_timed':len(durations),'median_ms':statistics.median(durations),
            'p95_ms':sorted(durations)[int(.95*len(durations))]})
    report={'scope':'Warm in-process exact-filter retrieval on 42 development/regression cases; fixture setup excluded.',
            'results':rows,'deployed_bm25_fts_or_reranker':False,
            'limitations':['Small catalogs, no concurrency or model generation; not a SaaS load test.']}
    output.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
