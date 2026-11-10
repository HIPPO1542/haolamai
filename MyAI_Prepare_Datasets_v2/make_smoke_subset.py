#!/usr/bin/env python3
"""Prepare a tiny real QLoRA smoke dataset from the already-prepared SFT splits.
Do not confuse this with model evaluation or the full training job.
"""
import argparse, json, random, sys
from pathlib import Path

def main():
 a=argparse.ArgumentParser()
 a.add_argument('--project-root',default='.')
 a.add_argument('--output',default='data/prepared_v2')
 args=a.parse_args()
 d=Path(args.project_root).resolve()/args.output
 sources={'smoke_train':(d/'train.jsonl',120),'smoke_valid':(d/'validation.jsonl',24)}
 rng=random.Random(12345)
 for name,(src,n) in sources.items():
  if not src.is_file():raise SystemExit(f'ERROR missing {src}')
  dst=d/(name+'.jsonl')
  if dst.exists():raise SystemExit(f'ERROR: {dst} already exists (refuse overwrite).')
  lines=src.read_text(encoding='utf-8').splitlines()
  if len(lines)<n:raise SystemExit(f'ERROR {src} has fewer than {n} rows')
  selected=rng.sample(lines,n)
  for item in selected:json.loads(item)
  dst.write_text('\n'.join(selected)+'\n',encoding='utf-8')
  print(f'CREATED {dst} ({n} rows, from existing split)')
 print('Smoke train is only a compatibility test; never compare its quality to full fine-tune.')
if __name__=='__main__':main()
