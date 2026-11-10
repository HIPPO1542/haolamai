#!/usr/bin/env python3
"""Offline audit of two downloaded product-search datasets. Stdlib only.
No source files modified; never put WANDS relevance labels directly in MyAI SFT.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import re
import sys
from datetime import datetime, timezone


def search_files(root: Path, suffixes={'.csv', '.jsonl'}):
    if not root.exists():
        return []
    return sorted(p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in suffixes
                  and '.cache' not in p.parts and '.git' not in p.parts)


def table_info(path: Path):
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        head = f.read(8192)
        f.seek(0)
        try:
            delimiter = csv.Sniffer().sniff(head, delimiters='\t,;').delimiter
        except csv.Error:
            delimiter = '\t' if '\t' in head.partition('\n')[0] else ','
        reader = csv.DictReader(f, delimiter=delimiter)
        cols = [c.strip() for c in (reader.fieldnames or []) if c]
        return cols, delimiter


def csv_rows(path: Path):
    _, d = table_info(path)
    csv.field_size_limit(min(sys.maxsize, 2**31-1))
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f, delimiter=d)


def inspect_intent(root: Path):
    files = search_files(root)
    candidates=[]
    for f in files:
        try:
            if f.suffix=='.csv':
                cols, _ = table_info(f)
                if {'text','label'} <= set(cols): candidates.append(f)
            elif f.suffix=='.jsonl':
                with f.open(encoding='utf-8-sig') as h:
                    for line in h:
                        if line.strip():
                            obj=json.loads(line)
                            if isinstance(obj,dict) and {'text','label'} <= set(obj):candidates.append(f)
                            break
        except (ValueError, UnicodeError, OSError, csv.Error):
            continue
    res={'status':'OK' if candidates else 'MISSING', 'source_dir':str(root),
         'files_found':[str(p.relative_to(root)) for p in files[:80]],
         'input_files':[], 'total_rows':0, 'labels':{}, 'empty_texts':0,
         'identical_text_duplicates':0, 'conflicting_duplicate_labels':0,
         'sample_texts':[], 'notes':[]}
    if not candidates:
        res['notes'].append('No readable CSV/JSONL with text,label columns found. Examine files_found; may require extracting archives or converting Parquet.')
        return res
    label_counts=Counter(); texts={}; unique_examples=[]; conflict=0; duplicate=0
    for f in candidates:
        count=0
        src=csv_rows(f) if f.suffix=='.csv' else (json.loads(x) for x in f.open('r',encoding='utf-8-sig') if x.strip())
        for row in src:
            count+=1
            t=str(row.get('text','')).strip()
            label=str(row.get('label','')).strip()
            if not t or not label:
                res['empty_texts']+=1
                continue
            label_counts[label]+=1
            key=re.sub(r'\s+',' ',t).strip().casefold()
            if key in texts:
                duplicate+=1
                if texts[key]!=label:conflict+=1
            else:
                texts[key]=label
            if len(unique_examples)<5:
                unique_examples.append({'text':t[:160], 'label':label})
        res['input_files'].append({'file':str(f.relative_to(root)), 'rows':count})
        res['total_rows']+=count
    res['labels']=dict(label_counts.most_common())
    res['identical_text_duplicates']=duplicate
    res['conflicting_duplicate_labels']=conflict
    res['sample_texts']=unique_examples
    if duplicate:res['notes'].append('Deduplicate and group identical customer texts before train/eval split.')
    if conflict:res['notes'].append('Same customer text has conflicting intent labels; quarantine before training.')
    if 'search_product' not in label_counts:
        res['notes'].append('No search_product class was found; check label mapping.')
    return res


def inspect_wands(root: Path):
    files = {x.name:x for x in search_files(root, suffixes={'.csv'}) if x.name in ('product.csv','query.csv','label.csv')}
    res={'status':'OK' if len(files)==3 else 'MISSING', 'source_dir':str(root),
         'input_files':{x:str(p.relative_to(root)) for x,p in files.items()},
         'products':0,'queries':0,'judgments':0,'labels':{},
         'unknown_product_references':0, 'unknown_query_references':0,
         'duplicate_judgments':0, 'conflicting_duplicate_judgments':0,
         'duplicate_product_ids':0, 'duplicate_query_ids':0,
         'sample_queries':[], 'notes':[]}
    if len(files)!=3:
        missing=set(('product.csv','query.csv','label.csv'))-set(files)
        res['notes'].append('Missing WANDS dataset files: '+', '.join(sorted(missing))+'; expected under wands/dataset/.')
        return res
    products=set(); queries=set()
    for row in csv_rows(files['product.csv']):
        res['products']+=1
        x=str(row.get('product_id','')).strip()
        if x in products:res['duplicate_product_ids']+=1
        if x:products.add(x)
    for row in csv_rows(files['query.csv']):
        res['queries']+=1
        x=str(row.get('query_id','')).strip()
        if x in queries:res['duplicate_query_ids']+=1
        if x:queries.add(x)
        if len(res['sample_queries'])<5:res['sample_queries'].append(str(row.get('query',''))[:160])
    labels=Counter();pairs={}
    for row in csv_rows(files['label.csv']):
        res['judgments']+=1
        q=str(row.get('query_id','')).strip();p=str(row.get('product_id','')).strip()
        if q not in queries:res['unknown_query_references']+=1
        if p not in products:res['unknown_product_references']+=1
        label=str(row.get('label','')).strip()
        if (q,p) in pairs:
            res['duplicate_judgments']+=1
            if pairs[(q,p)]!=label:res['conflicting_duplicate_judgments']+=1
        else:pairs[(q,p)]=label
        labels[label]+=1
    res['labels']=dict(labels.most_common())
    if res['unknown_product_references'] or res['unknown_query_references']:
        res['status']='INVALID'
        res['notes'].append('Some relevance labels reference missing products or queries.')
    if res['duplicate_judgments']:
        res['notes'].append('Duplicate query/product judgments detected; deduplicate before ranking evaluation.')
    if res['conflicting_duplicate_judgments']:
        res['notes'].append('Conflicting relevance judgments require quarantine or a documented resolution; do not choose a label silently.')
    res['notes'].append('WANDS is an English search-relevance benchmark. Keep query-level evaluation holdout; do not mix its labeled pairs into customer service SFT.')
    return res


def main():
    ap=argparse.ArgumentParser(description='Validate downloaded intent and WANDS sources, offline and read-only')
    ap.add_argument('--project-root',default='.')
    ap.add_argument('--intent-dir',default='datasets/raw/vi_ecommerce_intent')
    ap.add_argument('--wands-dir',default='datasets/raw/wands')
    ap.add_argument('--output',default='data/search_data_preflight/report.json')
    a=ap.parse_args()
    root=Path(a.project_root).resolve()
    def loc(arg):
        p=Path(arg)
        return p.resolve() if p.is_absolute() else (root/p).resolve()
    i=inspect_intent(loc(a.intent_dir))
    w=inspect_wands(loc(a.wands_dir))
    report={'audit':'Source-file integrity and dataset shape only, NOT model performance',
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'intent':i,'wands':w,
            'next_steps':['Keep full original datasets untouched.',
                          'Use intent labels for routing evaluation (or separate routing SFT), never as product facts.',
                          'Use WANDS as held-out relevance test / retrieval ranker data; no price/stock ground truth.',
                          'Before combining with MyAI train: check class distribution, leakage and business-domain safety.']}
    out=loc(a.output)
    if not out.is_relative_to(root):ap.error('Output must be inside the project root')
    if out.is_relative_to(loc(a.intent_dir)) or out.is_relative_to(loc(a.wands_dir)):
        ap.error('Output must not modify dataset sources')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Vietnamese intent:',i['status'],'| rows:',i['total_rows'],'| classes:',len(i['labels']), '| identical texts:',i['identical_text_duplicates'])
    print('Intent labels:',json.dumps(i['labels'],ensure_ascii=False))
    print('WANDS:',w['status'],'| products:',w['products'],'| queries:',w['queries'],'| relevance labels:',w['judgments'])
    print('WANDS labels:',json.dumps(w['labels'],ensure_ascii=False))
    if i['notes']:print('Intent notes:','; '.join(i['notes']))
    if w['notes']:print('WANDS notes:','; '.join(w['notes']))
    print('REPORT:',out)
    print('NOTE: No source dataset and no SFT files were modified. No Qwen model training was run.')
    return 0 if i['status']=='OK' and w['status']=='OK' else 2

if __name__=='__main__':raise SystemExit(main())
