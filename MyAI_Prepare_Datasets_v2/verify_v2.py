#!/usr/bin/env python3
"""Dataset integrity verification and split-contamination checks; no GPU required."""
import argparse, collections, hashlib, json, re, sys
from pathlib import Path

def fp(x):
    v=json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).lower()
    return hashlib.sha256(v.encode()).hexdigest()

def norm_text(x):
    p=' '.join(m.get('content','') for m in x['prompt'] if m.get('role')=='user')
    a=' '.join(m.get('content','') for m in x['completion'] if m.get('role')=='assistant')
    s=re.sub(r'\s+',' ',p+'|'+a).strip().lower()
    return hashlib.sha256(s.encode()).hexdigest()

def scan(path):
    e=set();n=set();row_count=0;counts=collections.Counter()
    with path.open(encoding='utf-8-sig') as f:
        for idx,line in enumerate(f,1):
            try:r=json.loads(line)
            except Exception as exc:raise ValueError(f'{path} at line {idx}: {exc}')
            if not isinstance(r,dict) or not isinstance(r.get('prompt'),list) or not isinstance(r.get('completion'),list):
                raise ValueError(f'{path}:{idx} invalid prompt/completion lists')
            if not r['prompt'] or not r['completion'] or not isinstance(r['completion'][-1],dict) or r['completion'][-1].get('role')!='assistant':
                raise ValueError(f'{path}:{idx} invalid chat roles')
            for m in r['prompt']+r['completion']:
                if not isinstance(m,dict) or m.get('role') not in ('system','user','assistant') or not isinstance(m.get('content'),str) or not m['content'].strip():
                    raise ValueError(f'{path}:{idx} invalid message')
            if not any(m['role']=='user' for m in r['prompt']):raise ValueError(f'{path}:{idx} missing user')
            if re.search(r'<(?:think|tool_call|tools|tool_response)\b',r['completion'][-1]['content'],re.I):
                raise ValueError(f'{path}:{idx} latent tool/think markup')
            h=fp(r);c=norm_text(r)
            if h in e or c in n:raise ValueError(f'{path}:{idx} exact or normalized duplicate')
            e.add(h);n.add(c);row_count+=1
            ans=r['completion'][-1]['content'];counts['total_completion_chars']+=len(ans)
    if not row_count:raise ValueError(f'{path}: empty split')
    return row_count,e,n,counts

def main():
    a=argparse.ArgumentParser();a.add_argument('--project-root',default='.');a.add_argument('--output',default='data/prepared_v2')
    x=a.parse_args();out=(Path(x.project_root).resolve()/x.output)
    paths={k:out/(k+'.jsonl') for k in ('train','validation','test_external')}
    if not all(p.is_file() for p in paths.values()):raise SystemExit('ERROR: missing prepared_v2 JSONL files')
    result={k:scan(p) for k,p in paths.items()}
    for k,(n,_,__,stats) in result.items():print(f'PASS | {k}: {n} rows; avg completion length {stats["total_completion_chars"]/n:.0f} characters')
    for a,b in [('train','validation'),('train','test_external'),('validation','test_external')]:
        ex=result[a][1]&result[b][1];norm=result[a][2]&result[b][2]
        if ex or norm:raise RuntimeError(f'LEAKAGE: {a} and {b}, exact {len(ex)}, normalized {len(norm)}')
    assert (out/'myai_eval_cases.jsonl').is_file(), 'missing independent benchmark'
    n=sum(1 for v in (out/'myai_eval_cases.jsonl').open(encoding='utf-8') if v.strip())
    if (out/'audit_report.json').is_file():
        report=json.loads((out/'audit_report.json').read_text(encoding='utf-8'))
        expected=dict(report['candidate_counts'],myai_benchmark=report['independent_benchmark'])
    else:
        report=json.loads((out/'report.json').read_text(encoding='utf-8'))
        expected=report['output_counts']
    actual={'train':result['train'][0],'validation':result['validation'][0],
            'test_external':result['test_external'][0],'myai_benchmark':n}
    if expected!=actual:raise RuntimeError('counts disagree with dataset report')
    print(f'PASS | {n} independent benchmark items; all split-integrity tests passed')
    print('WARNING | This does not certify semantic correctness, grounding, privacy or model quality.')
if __name__=='__main__':main()
