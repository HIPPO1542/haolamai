"""Separate intent/ranking benchmarks, query-group splits and conflict quarantine.

Nothing here is chatbot SFT. Original sources and all existing tests stay intact.
Baseline parameters are fixed before running the heldout splits; no tuning loop.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from myai.retrieval import normalize
from myai.text_index import BM25Index


def canonical(text):
    return ' '.join(re.findall(r'[a-z0-9]+',normalize(text)))


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read_csv(path):
    csv.field_size_limit(2**31-1)
    with path.open(encoding='utf-8-sig',newline='') as stream:
        header=stream.readline(); stream.seek(0)
        yield from csv.DictReader(stream,delimiter='\t' if '\t' in header else ',')


def write_jsonl(path,records):
    with path.open('x',encoding='utf-8') as stream:
        for row in records:
            stream.write(json.dumps(row,ensure_ascii=False)+'\n')


def grouped_split(groups):
    ordered=sorted(groups,key=lambda key:digest('myai-v23-fixed-split:'+key))
    train_end=int(len(ordered)*.8); validation_end=int(len(ordered)*.9)
    return {key:'train' if i<train_end else 'validation' if i<validation_end else 'test'
            for i,key in enumerate(ordered)}


def intent_benchmark(source,output):
    groups=defaultdict(list)
    for line,row in enumerate(read_csv(source),2):
        groups[canonical(row['text'])].append({'source_line':line,'text':row['text'],'label':row['label']})
    conflicts={key:values for key,values in groups.items() if len({row['label'] for row in values})>1}
    records={key:values[0] for key,values in groups.items() if key not in conflicts}
    by_label=defaultdict(list)
    for key,row in records.items():by_label[row['label']].append(key)
    assignment={key:split for keys in by_label.values() for key,split in grouped_split(keys).items()}
    splits={name:[dict(row,question_group_sha256=digest(key)) for key,row in records.items() if assignment[key]==name]
            for name in ('train','validation','test')}
    output.mkdir()
    for split,values in splits.items():write_jsonl(output/(split+'.jsonl'),values)
    write_jsonl(output/'conflicts.jsonl',({'question_group_sha256':digest(key),'source_lines':[row['source_line'] for row in values],
        'labels':sorted({row['label'] for row in values})} for key,values in conflicts.items()))
    # A simple routing benchmark. Only training utterances become retrieval documents.
    labels={str(i):row['label'] for i,row in enumerate(splits['train'])}
    index=BM25Index((str(i),row['text']) for i,row in enumerate(splits['train']))
    confusion=Counter(); per_label=Counter(); correct=0
    for row in splits['test']:
        matches=index.search(row['text'],1)
        prediction=labels[matches[0][0]] if matches else 'UNKNOWN'
        confusion[(row['label'],prediction)]+=1;per_label[row['label']]+=1
        correct+=prediction==row['label']
    f1=[]
    for label in sorted(by_label):
        tp=confusion[label,label]
        fp=sum(count for (actual,predicted),count in confusion.items() if predicted==label and actual!=label)
        fn=sum(count for (actual,predicted),count in confusion.items() if actual==label and predicted!=label)
        f1.append(2*tp/max(2*tp+fp+fn,1))
    return {'source_rows':sum(len(values) for values in groups.values()), 'conflict_groups_quarantined':len(conflicts),
        'conflict_rows_quarantined':sum(len(values) for values in conflicts.values()),
        'same_label_duplicates_removed':sum(len(values)-1 for key,values in groups.items() if key not in conflicts),
        'counts':{name:len(values) for name,values in splits.items()},
        'test_routing_baseline':{'accuracy':correct/len(splits['test']),'macro_f1':sum(f1)/len(f1),
            'confusion':[{'actual':a,'predicted':p,'count':n} for (a,p),n in sorted(confusion.items())]},
        'question_group_overlap':0,'purpose':'Intent routing only; no catalog facts or chatbot SFT'}


def ranking_benchmark(source,output):
    products=list(read_csv(source/'product.csv'));queries=list(read_csv(source/'query.csv'))
    product_ids={row['product_id'] for row in products}
    query_by_id={row['query_id']:row for row in queries}
    assignment=grouped_split({canonical(row['query']) for row in queries})
    pairs=defaultdict(list)
    raw_judgments=0
    for line,row in enumerate(read_csv(source/'label.csv'),2):
        if row['product_id'] not in product_ids or row['query_id'] not in query_by_id:
            raise ValueError('Unknown relevance reference')
        pairs[(row['query_id'],row['product_id'])].append((line,row['label']));raw_judgments+=1
    clean={pair:values[0][1] for pair,values in pairs.items() if len({label for _,label in values})==1}
    conflicts={pair:values for pair,values in pairs.items() if len({label for _,label in values})>1}
    output.mkdir()
    query_records={split:[dict(row,question_group_sha256=digest(canonical(row['query']))) for row in queries
                        if assignment[canonical(row['query'])]==split] for split in ('train','validation','test')}
    for split,records in query_records.items():
        write_jsonl(output/(split+'_queries.jsonl'),records)
        query_ids={row['query_id'] for row in records}
        write_jsonl(output/(split+'_judgments.jsonl'),({'query_id':q,'product_id':p,'label':label}
            for (q,p),label in clean.items() if q in query_ids))
    write_jsonl(output/'conflicts.jsonl',({'query_id':pair[0],'product_id':pair[1],
        'source_lines':[line for line,_ in values],'labels':sorted({label for _,label in values})}
        for pair,values in conflicts.items()))
    # Fixed lexical features; query_class and relevance judgments never enter this index.
    index=BM25Index((row['product_id'], (' '+row['product_name'])*3+' '+row['product_class']+' '+row['category hierarchy']+' '+row['product_description']) for row in products)
    gold=defaultdict(dict)
    for (q,p),label in clean.items():gold[q][p]={'Exact':2,'Partial':1,'Irrelevant':0}[label]
    metrics=[]
    for query in query_records['test']:
        judgments=gold[query['query_id']]
        ranked=[doc_id for doc_id,_ in index.search(query['query'],10)]
        dcg=sum((2**judgments.get(doc_id,0)-1)/math.log2(rank+2) for rank,doc_id in enumerate(ranked))
        ideal=sum((2**grade-1)/math.log2(rank+2) for rank,grade in enumerate(sorted(judgments.values(),reverse=True)[:10]))
        positive={doc_id for doc_id,grade in judgments.items() if grade>0}
        metrics.append({'query_id':query['query_id'],'ndcg_at_10':dcg/ideal if ideal else 0,
            'recall_at_10':len(positive & set(ranked))/max(len(positive),1),
            'exact_mrr_at_10':next((1/(i+1) for i,doc_id in enumerate(ranked) if judgments.get(doc_id)==2),0),
            'unjudged_in_top10':sum(doc_id not in judgments for doc_id in ranked)})
    write_jsonl(output/'test_results_once.jsonl',metrics)
    return {'products':len(products),'queries':len(queries),'raw_judgments':raw_judgments,
        'duplicate_pair_rows':raw_judgments-len(pairs),'conflict_pairs_quarantined':len(conflicts),
        'conflict_rows_quarantined':sum(len(values) for values in conflicts.values()),
        'clean_unique_judgments':len(clean),'query_split_counts':{split:len(values) for split,values in query_records.items()},
        'test_lexical_baseline':{key:sum(row[key] for row in metrics)/len(metrics)
            for key in ('ndcg_at_10','recall_at_10','exact_mrr_at_10','unjudged_in_top10')},
        'question_group_overlap':0,'purpose':'Search relevance only; no price/stock facts or chatbot SFT',
        'evaluation_policy':'Unjudged products count as zero relevance; fixed BM25 baseline, no tuning on test.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs') or output.exists():parser.error('Use a new output directory under outputs')
    paths=[ROOT/'datasets/raw/vi_ecommerce_intent/intent_dataset.csv']+[ROOT/'datasets/raw/wands/dataset'/name for name in ('product.csv','query.csv','label.csv')]
    before={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    output.mkdir(parents=True)
    report={'intent':intent_benchmark(paths[0],output/'intent'),
            'wands':ranking_benchmark(paths[1].parent,output/'ranking'),'source_sha256':before,
            'trained_chatbot':False,'deployed_router_or_ranker':False}
    assert before=={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({name:{key:value for key,value in report[name].items() if key!='test_routing_baseline'} for name in ('intent','wands')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
