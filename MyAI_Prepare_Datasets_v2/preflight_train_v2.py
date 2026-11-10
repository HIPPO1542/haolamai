#!/usr/bin/env python3
"""Pre-rental offline sanity check: file hashes, sizes, relative token/length estimates."""
import argparse,json,hashlib,statistics
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--project-root',default='.');p.add_argument('--output',default='data/prepared_v2')
 x=p.parse_args();root=Path(x.project_root).resolve();d=root/x.output
 for n in ('train','validation','test_external'):
  path=d/(n+'.jsonl');lengths=[];count=0;sha=hashlib.sha256()
  for line in path.open('rb'):
   sha.update(line);obj=json.loads(line);count+=1
   lengths.append(sum(len(m['content']) for m in obj['prompt']+obj['completion']))
  if not lengths:raise ValueError('Empty data: '+n)
  print(f'{n:15} rows={count:5}  mean_chars={statistics.mean(lengths):.0f}  p95_chars={sorted(lengths)[int(len(lengths)*0.95)]:.0f}  sha256={sha.hexdigest()}')
 print('NOTE: chars are NOT token counts. Before renting, token-count using the local Qwen tokenizer if available.')
 print('NOTE: Select reviewed data explicitly with --train/--valid. Candidate quality review is still required.')
if __name__=='__main__':main()
