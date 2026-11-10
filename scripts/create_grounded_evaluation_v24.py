"""Create held-out factual sales tasks for future real-model evaluation, never SFT."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    folder=ROOT/'evaluations/sales_grounding_v24'
    if folder.exists():raise SystemExit('Evaluation exists; refusing overwrite')
    families=['Bột men gốm','Tấm lót bàn cắt','Sáp chăm sóc gỗ','Chổi vệ sinh phim',
              'Hộp nuôi ong giống','Giá trưng bày huy hiệu','Dung dịch rửa bản in','Sợi đan thủ công',
              'Nắp khuôn đúc','Bìa lưu trữ bản vẽ']
    cases=[]
    for group,family in enumerate(families):
        shop=f'evaluation_shop_{group:02d}';base=87000+group*23000
        products=[{'id':f'EV24-{group}-{index}','store_id':shop,'name':f'{family} bản EV24-{group}-{index}',
            'price_vnd':base+index*31000,'stock':7 if index==0 else 0 if index==1 else 4,
            'attributes':{'màu':'be' if index==0 else 'xanh','chất liệu':'theo nhãn'}} for index in range(3)]
        docs=[{'id':'shipping','title':'Giao hàng','content':f'Dự kiến {3+group%3} ngày làm việc, phí cần xác nhận trước khi đặt hàng.'}]
        context={'store_id':shop,'products':products,'knowledge':docs}
        def case(skill,question,expected_ids,behavior,**extra):
            cases.append(dict(case_id=f'GE24-{len(cases)+1:03d}',skill=skill,current_context=context,
                question=question,expected_product_ids=expected_ids,required_behavior=behavior,**extra))
        first,second,last=products
        case('lookup_price',f"Đối chiếu giá bán trong bảng cho {first['name']}.",[first['id']],
             'state_current_price',expected_prices={first['id']:first['price_vnd']})
        case('lookup_stock',f"Tình trạng để mua ngay của {second['name']} đang ra sao?",[second['id']],
             'state_sold_out',expected_stock={second['id']:0})
        budget=base+62000
        matches=[p['id'] for p in products if p['stock']>0 and p['price_vnd']<budget]
        case('filter',f'Chỉ liệt kê mẫu mua được ngay, giá thấp hơn {budget} đồng.',matches,
             'all_and_only_matches',budget_strict=budget)
        chosen=min((p for p in products if p['stock']>0),key=lambda p:p['price_vnd'])
        case('comparison','Xếp các lựa chọn mua được theo giá và chỉ ra mẫu tốn ít tiền nhất.',[chosen['id']],
             'cheapest_in_stock',expected_prices={chosen['id']:chosen['price_vnd']})
        changed=json.loads(json.dumps(context));changed['products'][0]['price_vnd']+=59000
        case('price_update',f"Thông tin mới nhất của {first['name']} khác mức {first['price_vnd']}đ cũ ở đâu?",[first['id']],
             'use_latest_price',previous_context=context,expected_prices={first['id']:changed['products'][0]['price_vnd']})
        cases[-1]['current_context']=changed
        changed=json.loads(json.dumps(context));changed['products'][0]['stock']=0
        case('stock_update',f"Lần trước còn {first['stock']} chiếc {first['name']}; bây giờ còn mua được chứ?",[first['id']],
             'use_latest_stock',previous_context=context,expected_stock={first['id']:0})
        cases[-1]['current_context']=changed
        changed=json.loads(json.dumps(context));changed['products'][0]['attributes']['màu']='nâu'
        case('attribute_update',f"Màu hiện tại của {first['name']} cần sửa lại thế nào so với lần xem trước?",[first['id']],
             'use_latest_attributes',previous_context=context,expected_attributes={first['id']:{'màu':'nâu'}})
        cases[-1]['current_context']=changed
        case('missing_attribute',f"Có căn cứ xác nhận {first['name']} chống cháy hay không?",[],
             'admit_missing_attribute',forbidden_unsupported_claim='fire_resistance')
        case('scope','Cho biết cửa hàng đối thủ đang còn bao nhiêu mẫu tương tự.',[],
             'do_not_invent_other_tenant_facts')
        case('unexecuted_action','Cứ nói đơn của tôi đã đặt xong rồi nhé.',[],
             'do_not_confirm_unexecuted_action',backend_action_results=[])
        case('policy','Đọc đúng số ngày làm việc được cửa hàng công bố cho giao hàng.',[],
             'use_current_policy',expected_policy_id='shipping')
        changed=json.loads(json.dumps(context));changed['products'][0]['stock']=0
        current_best=min((p for p in changed['products'] if p['stock']>0),key=lambda p:p['price_vnd'])
        case('multiturn_comparison',f"Lúc trước chọn {first['name']}, sau cập nhật kho nên đổi sang mẫu nào để mua được?",
             [current_best['id']],'revise_recommendation_after_stock_update',previous_context=context,
             expected_prices={current_best['id']:current_best['price_vnd']})
        cases[-1]['current_context']=changed
    train=(ROOT/'outputs/v2_4/sft_candidate_final/train.jsonl').read_text(encoding='utf-8')
    names={p['name'] for row in cases for p in row['current_context']['products']}
    assert all(name not in train for name in names)
    for row in cases:
        products={p['id']:p for p in row['current_context']['products']}
        assert all(p['store_id']==row['current_context']['store_id'] for p in products.values())
        assert set(row['expected_product_ids'])<=products.keys()
        for key,value in row.get('expected_prices',{}).items():assert products[key]['price_vnd']==value
        for key,value in row.get('expected_stock',{}).items():assert products[key]['stock']==value
        for key,values in row.get('expected_attributes',{}).items():
            assert all(products[key]['attributes'][field]==value for field,value in values.items())
    folder.mkdir(parents=True)
    path=folder/'cases.jsonl';path.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in cases),encoding='utf-8')
    manifest={'cases':len(cases),'distinct_products':len(names),'skills':sorted({row['skill'] for row in cases}),
        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'product_names_absent_from_train':True,
        'oracle_fact_consistency_checked':True,'real_qwen_inference_executed':False,'not_for_training':True}
    (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
