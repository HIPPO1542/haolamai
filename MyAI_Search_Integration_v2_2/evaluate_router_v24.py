"""Select a lexical intent baseline on validation only, score existing test once."""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from myai.text_index import BM25Index


def read_rows(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]


def measure(index,labels,rows,k,all_labels):
    confusion=Counter();durations=[]
    for row in rows:
        start=time.perf_counter();votes=defaultdict(float)
        for doc_id,score in index.search(row['text'],k):votes[labels[doc_id]]+=score
        prediction=sorted(votes,key=lambda label:(-votes[label],label))[0] if votes else 'UNKNOWN'
        durations.append((time.perf_counter()-start)*1000);confusion[row['label'],prediction]+=1
    f1=[]
    for label in all_labels:
        tp=confusion[label,label]
        fp=sum(n for (actual,predicted),n in confusion.items() if predicted==label and actual!=label)
        fn=sum(n for (actual,predicted),n in confusion.items() if actual==label and predicted!=label)
        f1.append(2*tp/max(2*tp+fp+fn,1))
    return {'k':k,'rows':len(rows),'accuracy':sum(n for (a,p),n in confusion.items() if a==p)/len(rows),
        'macro_f1':sum(f1)/len(f1),'median_query_ms':statistics.median(durations),
        'p95_query_ms':sorted(durations)[int(.95*len(durations))],
        'confusion':[{'actual':a,'prediction':p,'count':n} for (a,p),n in sorted(confusion.items())]}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs/v2_4') or output.exists():parser.error('Use a new v2.4 report path')
    source=ROOT/'outputs/v2_3/search_benchmarks/intent'
    splits={name:read_rows(source/(name+'.jsonl')) for name in ('train','validation','test')}
    groups={name:{row['question_group_sha256'] for row in rows} for name,rows in splits.items()}
    assert not groups['train']&groups['validation'] and not groups['train']&groups['test'] and not groups['validation']&groups['test']
    labels={str(i):row['label'] for i,row in enumerate(splits['train'])}
    all_labels=sorted(set(labels.values()))
    start=time.perf_counter();index=BM25Index((str(i),row['text']) for i,row in enumerate(splits['train']))
    build_ms=(time.perf_counter()-start)*1000
    validation=[measure(index,labels,splits['validation'],k,all_labels) for k in (1,3,5,7)]
    chosen=sorted(validation,key=lambda row:(-row['macro_f1'],-row['accuracy'],row['k']))[0]['k']
    test=measure(index,labels,splits['test'],chosen,all_labels)
    report={'scope':'Intent classification only; not customer-answer/product fact evaluation',
        'selection':'k chosen by validation macro-F1, then accuracy, then smaller k; no test tuning',
        'index_build_ms':build_ms,'validation':validation,'test_once':test,
        'deployed_into_backend':False,'question_groups_disjoint':True}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in test.items() if key!='confusion'},indent=2))


if __name__=='__main__':main()
