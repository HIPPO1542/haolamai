#!/usr/bin/env python3
"""MyAI quality gate v2.1. Pure stdlib, offline, read-only inputs.
Creates distinct *candidate* SFT splits and annotated human-review queues.
This is a heuristic audit; NOT proof of groundedness or production readiness.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

SYSTEM_ACTION_TAG = 'KẾT QUẢ HỆ THỐNG'
AMOUNT = re.compile(r'(?<!\w)(?:\d{1,3}(?:[.,]\d{3})+|\d{2,9})\s*(?:₫|đồng|vnđ|vnd|đ|k)(?!\w)', re.I)
PII = re.compile(r'(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9,10}(?!\d)|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', re.I)
PROMPT_LEAK = re.compile(r'(?i)(?:bạn là|mình là|tôi là|em là|trợ lý)\s+(?:empathai|saas\s*chatbot)|\bEmpathAI\b')
CLAIM_ACTIONS = {
 'booking': re.compile(r'(?i)(?:đã|vừa)\s+(?:đặt\s+lịch|xác\s+nhận\s+lịch|giữ\s+chỗ)|(?:lịch\s+hẹn|đặt\s+lịch).{0,24}(?:đã\s+được\s+xác\s+nhận|thành\s+công)'),
 'order': re.compile(r'(?i)(?:đã|vừa)\s+(?:đặt\s+hàng|lên\s+đơn|chốt\s+đơn|tạo\s+đơn|xác\s+nhận\s+đơn)|đặt\s+hàng\s+thành\s+công'),
 'refund': re.compile(r'(?i)(?:đã|vừa)\s+(?:hoàn\s+tiền|chuyển\s+tiền\s+hoàn)|tiền\s+(?:đã\s+được|được)\s+hoàn'),
 'cancel': re.compile(r'(?i)(?:đã|vừa)\s+(?:hủy\s+(?:đơn|lịch)|hoàn\s+tất\s+thủ\s+tục\s+hủy)'),
 'handoff': re.compile(r'(?i)(?:đã|đang)\s+(?:chuyển\s+(?:bạn|anh|chị|yêu\s+cầu|thông\s+tin)|kết\s+nối\s+(?:bạn|anh|chị))\s+(?:đến|cho|sang|với)\s+(?:nhân\s+viên|chuyên\s+viên|bộ\s+phận|quản\s+lý|bác\s+sĩ)|(?:đã|vừa)\s+gửi\s+(?:email|tin\s+nhắn|mã\s+giảm\s+giá)'),
}
EVIDENCE = {
 'booking': re.compile(r'(?i)"(?:status|booking_status)"\s*:\s*"(?:confirmed|booked|success|completed)"|"booking_id"\s*:'),
 'order': re.compile(r'(?i)"(?:status|order_status)"\s*:\s*"(?:confirmed|created|placed|success|completed)"|"order_id"\s*:'),
 'refund': re.compile(r'(?i)"(?:status|refund_status)"\s*:\s*"(?:refunded|refund_completed|completed)"'),
 'cancel': re.compile(r'(?i)"(?:status|cancel_status)"\s*:\s*"(?:cancelled|canceled)"'),
 'handoff': re.compile(r'(?i)"(?:status|handoff_status)"\s*:\s*"(?:transferred|connected|sent|success)"'),
}
NEEDS_ATTENTION = re.compile(r'(?i)\b(?:augmentin|kháng\s+sinh|liều\s+lượng\s+thuốc|toa\s+thuốc|phác\s+đồ\s+điều\s+trị)\b')


def msgs_to_string(msgs, role):
 if not isinstance(msgs,list):return ''
 return '\n'.join(m.get('content','') for m in msgs if isinstance(m,dict) and m.get('role')==role and isinstance(m.get('content'),str))

def user_string(row):return msgs_to_string(row.get('prompt'), 'user')
def assistant_string(row):return msgs_to_string(row.get('completion'), 'assistant')

def money_canonical(s):
 s=s.lower().replace('vnđ','đ').replace('vnd','đ').replace('đồng','đ').replace('₫','đ')
 m=re.match(r'([0-9.,]+)\s*(k|đ)?',s)
 if not m:return None
 n,unit=m.group(1),m.group(2)
 try:
  if unit=='k':return int(float(n.replace(',','.'))*1000)
  return int(n.replace('.','').replace(',',''))
 except ValueError:return None

def rule_flags(row):
 p=user_string(row); a=assistant_string(row)
 hard=[]; review=[]
 if not p or not a:hard.append('empty_prompt_or_answer')
 if PROMPT_LEAK.search(a):hard.append('other_chatbot_identity_in_answer')
 for kind,pat in CLAIM_ACTIONS.items():
  if pat.search(a):
   tool=p.split(SYSTEM_ACTION_TAG,1)[1] if SYSTEM_ACTION_TAG in p else ''
   if not EVIDENCE[kind].search(tool):
    hard.append('unverified_action_'+kind)
 if NEEDS_ATTENTION.search(p+' '+a):review.append('medical_or_regulated_context')
 if PII.search(p+' '+a):review.append('possible_pii')
 prices=[money_canonical(x) for x in AMOUNT.findall(a)]
 prices=[x for x in prices if x is not None]
 if prices:
  # Compare converted numeric amounts (so "25k" and "25.000đ" agree).
  fact_prices={money_canonical(x) for x in AMOUNT.findall(p)}
  # also scan JSON numeric facts, especially price_vnd (150000) with no unit.
  fact_prices.update(int(n) for n in re.findall(r'"(?:price|price_vnd|total|shipping_fee|discount_vnd)"\s*:\s*(\d+)',p))
  if any(n not in fact_prices for n in prices):review.append('answer_money_not_evidenced')
 if a.rstrip().endswith('?') and len(a)>300:review.append('long_answer_review')
 return sorted(set(hard)),sorted(set(review))

def norm_q(row):
 p=user_string(row)
 # isolate current question; for identical customer questions across splits, human review only.
 q=p.rsplit('CÂU HỎI CỦA KHÁCH:',1)[-1]
 q=q.split(SYSTEM_ACTION_TAG)[0]
 q=re.sub(r'\s+',' ',q).strip().lower()
 return q

def sample_redact(s,n=260):return PII.sub('[REDACTED]',s[:n].replace('\n',' | '))

def read_jsonl(path):
 out=[]
 with path.open(encoding='utf-8-sig') as f:
  for idx,line in enumerate(f,1):
   if not line.strip():continue
   obj=json.loads(line)
   if not isinstance(obj,dict):raise ValueError(f'{path}:{idx} not JSON object')
   out.append(obj)
 return out

def write_jsonl(path,rows):
 with path.open('w',encoding='utf-8',newline='\n') as f:
  for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')

def csv_out(path,rows):
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['split','row_number','severity','reasons','question_preview_redacted','answer_preview_redacted'])
  for split,idx,severity,reasons,r in rows:
   w.writerow([split,idx,severity,';'.join(reasons),sample_redact(user_string(r)),sample_redact(assistant_string(r))])

def main(args=None):
 ap=argparse.ArgumentParser(description='Create candidate cleaned dataset and review queues; NEVER overwrite input')
 ap.add_argument('--project-root',default='.')
 ap.add_argument('--input-dir',default='data/prepared_v2')
 ap.add_argument('--output-dir',default='data/prepared_v2_1_review')
 opts=ap.parse_args(args)
 root=Path(opts.project_root).resolve()
 src=(root/opts.input_dir).resolve();dst=(root/opts.output_dir).resolve()
 if not src.is_relative_to(root) or not dst.is_relative_to(root) or src==dst:ap.error('Input/output must be separate folders within project root')
 if dst.exists() and any(dst.iterdir()):ap.error('Output already exists and is not empty. Nothing overwritten.')
 for f in ['train.jsonl','validation.jsonl','test_external.jsonl','myai_eval_cases.jsonl']:
  if not (src/f).is_file():ap.error('Missing input '+str(src/f))
 data={s:read_jsonl(src/f'{s}.jsonl') for s in ['train','validation','test_external']}
 bench=read_jsonl(src/'myai_eval_cases.jsonl')
 accepted={}; hard=[]; review=[];hard_c=collections.Counter();review_c=collections.Counter()
 for split,rows in data.items():
  accept=[]
  for idx,row in enumerate(rows,1):
   h,m=rule_flags(row)
   if h:
    hard.append((split,idx,'HIGH_REVIEW',h,row));hard_c.update(h)
   else:accept.append(row)
   if m:
    review.append((split,idx,'MEDIUM_REVIEW',m,row));review_c.update(m)
  accepted[split]=accept
 questions={s:set(norm_q(r) for r in rows if norm_q(r)) for s,rows in data.items()}
 overlap={f'{a}_vs_{b}':len(questions[a]&questions[b]) for a,b in [('train','validation'),('train','test_external'),('validation','test_external')]}
 dst.mkdir(parents=True,exist_ok=True)
 for s,rows in accepted.items():write_jsonl(dst/f'{s}.jsonl',rows)
 write_jsonl(dst/'myai_eval_cases.jsonl',bench)
 csv_out(dst/'high_risk_review.csv',hard)
 csv_out(dst/'medium_risk_review.csv',review)
 report={
  'audit_type':'HEURISTIC ONLY: high-risk records withheld from candidate, not manually validated',
  'original_counts':{k:len(v) for k,v in data.items()},
  'candidate_counts':{k:len(v) for k,v in accepted.items()},
  'independent_benchmark':len(bench),
  'high_risk_records':len(hard),'high_risk_by_reason':dict(hard_c),
  'medium_risk_records':len(review),'medium_risk_by_reason':dict(review_c),
  'exact_customer_question_overlap_counts_including_context_variations':overlap,
  'limitations':['Some high-risk flags may be false positives; review before discarding permanently',
    'Some wrong facts or cross-store answers remain uncaught',
    'Medium-risk records remain in candidate until manual review',
    'No semantic duplicate, license/provenance or human quality certification',
    'No model was trained or evaluated'],
  'input_dir':str(src), 'output_dir':str(dst),
 }
 (dst/'audit_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({k:v for k,v in report.items() if k not in ('input_dir','output_dir','limitations')},indent=2,ensure_ascii=False))
 print('IMPORTANT: This is a candidate only. Inspect review files before paid fine-tuning.')
 return 0

if __name__=='__main__':sys.exit(main())
