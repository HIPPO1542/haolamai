"""Evaluate existing retrieval cases against a scratch catalog; no Qwen or training."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from myai.db import connect, initialize, add_store, add_product, add_knowledge
from myai.retrieval import retrieve, normalize


def fixture(conn):
    initialize(conn)
    pack = ROOT/'MyAI_Data_Pack_v1'
    for store, filename in [('food01', 'snacks_products.csv'), ('fashion01', 'fashion_products.csv')]:
        add_store(conn, store, 'Offline fixture', store)
        with (pack/'01_database'/filename).open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                add_product(conn, dict(id=row['id'], store_id=store, name=row['name'],
                    price_vnd=int(row['price_vnd']), stock=int(row['stock']), description=row['description'],
                    attributes=json.loads(row['attributes_json']), active=int(row['active'])))
    for line in (pack/'02_policies/policies.jsonl').read_text(encoding='utf-8').splitlines():
        doc = json.loads(line)
        add_knowledge(conn, doc['id'], doc['store_id'], doc['title'], doc['content'])


def check(case, products, docs):
    behavior = case['required_behavior']
    ids = [product['id'] for product in products]
    expected = case['expected_product_ids']
    scoped = all(item['store_id'] == case['store_id'] for item in products + docs)
    if not scoped:
        return False, 'cross_store_source'
    if behavior == 'must_not_recommend_inactive':
        return not set(expected) & set(ids), 'inactive_excluded'
    if behavior == 'only_matching_products':
        valid = bool(products) and all(p['price_vnd'] < 30000 and 'khong cay' in normalize(str(p)) for p in products)
        return valid, 'price_and_non_spicy'
    if behavior == 'only_matching_variants':
        valid = bool(products) and all('ao' in normalize(p['name']) and p['stock'] > 0
            and normalize(p['attributes'].get('màu')) == 'den'
            and p['attributes'].get('size') == 'L' for p in products)
        return valid, 'color_size_stock'
    if expected:
        valid = bool(products) and ids[0] == expected[0] and set(ids) <= set(expected)
        if case['expected_price_vnd'] is not None:
            valid &= bool(products) and products[0]['price_vnd'] == case['expected_price_vnd']
        if case['expected_stock'] is not None:
            valid &= bool(products) and products[0]['stock'] == case['expected_stock']
        return valid, 'expected_product_and_facts'
    if 'policy' in behavior or behavior in ('food_policy_not_fashion', 'fashion_policy_not_food'):
        return bool(docs) and not products, 'scoped_policy_source'
    return not products, 'no_unrelated_product'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--cases', default=str(ROOT/'MyAI_Data_Pack_v1/04_evaluation/myai_eval_cases.jsonl'))
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to(ROOT) or any(output.is_relative_to(ROOT/name) for name in ('data', 'datasets', 'models', 'adapters')):
        parser.error('Output must stay in workspace, outside protected inputs')
    cases = [json.loads(line) for line in Path(args.cases).read_text(encoding='utf-8').splitlines() if line]
    results = []
    for case in cases:
        # Each scenario starts fresh; case mutations never affect another scenario.
        conn = connect(':memory:')
        try:
            fixture(conn)
            if case['case_id'] == 'T123':
                conn.execute("UPDATE products SET price_vnd=27000 WHERE store_id='food01' AND id='F009'")
            elif case['case_id'] == 'T124':
                conn.execute("UPDATE products SET stock=0 WHERE store_id='fashion01' AND id='A005'")
            elif case['case_id'] == 'T125':
                conn.execute("UPDATE products SET active=0 WHERE store_id='food01' AND id='F001'")
            elif case['case_id'] == 'T126':
                add_product(conn, dict(id='A999', store_id='fashion01', name='Giày thể thao',
                                       price_vnd=299000, stock=3))
            conn.commit()
            products, docs = retrieve(conn, case['store_id'], case['question'])
            passed, criterion = check(case, products, docs)
            results.append({'case_id': case['case_id'], 'passed': passed, 'criterion': criterion,
                'product_ids': [product['id'] for product in products],
                'knowledge_ids': [doc['id'] for doc in docs]})
        finally:
            conn.close()
    report = {'scope': 'Retrieval and source facts only; NOT model response quality',
        'total': len(results), 'passed': sum(row['passed'] for row in results),
        'criteria': dict(Counter(row['criterion'] for row in results)), 'cases': results,
        'limitations': ['Behavior-only cases cannot establish response safety without real inference.',
            'Existing public project cases were used for regression development; use a new blind holdout for acceptance.']}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print('Retrieval:', report['passed'], '/', report['total'])
    for row in results:
        if not row['passed']:
            print('FAIL', row['case_id'], row['criterion'], row['product_ids'], row['knowledge_ids'])
    return int(report['passed'] != report['total'])


if __name__ == '__main__':
    raise SystemExit(main())
