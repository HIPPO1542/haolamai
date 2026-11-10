"""Real-model evaluation: requires downloaded Qwen weights and trained adapter.

This is a small automated regression suite, not a substitute for human evaluation.
"""
import argparse
import json
from pathlib import Path
from myai.db import connect,initialize,add_store,add_product
from myai.engine import LocalQwen,SalesAssistant

CASES=[
 ('snacks','Rong biển cháy tỏi giá bao nhiêu?',20000,'rong biển'),
 ('snacks','Shop có món không cay dưới 30k không?',20000,'rong biển'),
 ('fashion','Áo thun cotton có size XL không?',150000,'áo thun'),
 ('fashion','Áo màu đen giá bao nhiêu?',150000,'áo thun'),
 ('snacks','Áo thun cotton giá bao nhiêu?',None,None),
 ('fashion','Rong biển cháy tỏi bao nhiêu?',None,None),
]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',default='models/Qwen3.5-9B')
    p.add_argument('--adapter',default='adapters/myai-sales-v0.3-9B')
    p.add_argument('--output',default='data/evaluation.json')
    p.add_argument('--inference-4bit',action=argparse.BooleanOptionalAction,default=True)
    args=p.parse_args()
    conn=connect(':memory:');initialize(conn)
    add_store(conn,'snacks','Cửa hàng ăn vặt','Đồ ăn')
    add_store(conn,'fashion','Cửa hàng quần áo','Quần áo')
    add_product(conn,{'id':'01','store_id':'snacks','name':'Rong biển cháy tỏi',
        'price_vnd':20000,'stock':8,'description':'Không cay, giòn thơm.'})
    add_product(conn,{'id':'01','store_id':'fashion','name':'Áo thun cotton',
        'price_vnd':150000,'stock':5,'description':'Co giãn nhẹ.',
        'attributes':{'màu':['đen','trắng'],'size':['M','L','XL']}})
    ai=SalesAssistant(conn,LocalQwen(args.model,args.adapter,quantize=args.inference_4bit))
    results=[]
    for store,q,expected_price,expected_name in CASES:
        try:
            out=ai.respond(store,q)
            expected_source=bool(expected_price)
            ok=(bool(out['sources'])==expected_source and
                (not expected_source or out['generated_by_ai']) and
                (expected_name is None or expected_name in out['answer'].lower()) and
                (expected_price is None or any(s.get('price_vnd')==expected_price for s in out['sources'])))
            results.append({'store':store,'question':q,'answer':out['answer'],
                'source_count':len(out['sources']),'generated_by_ai':out['generated_by_ai'],
                'automated_check_passed':ok})
            print('PASS' if ok else 'FAIL',q,'=>',out['answer'])
        except Exception as exc:
            results.append({'store':store,'question':q,'error':str(exc),'automated_check_passed':False})
            print('ERROR',q,exc)
    report={'total':len(results),'checks_passed':sum(r['automated_check_passed'] for r in results),
            'warning':'Automated checks do not establish that responses are fully truthful or commercially safe.',
            'cases':results}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Saved',args.output)
    conn.close()
    return 0 if report['checks_passed'] == report['total'] else 1

if __name__=='__main__':raise SystemExit(main())
