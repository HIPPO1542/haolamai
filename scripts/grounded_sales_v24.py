"""Rule-generated sales examples with independent numeric gold verification.

The oracle reads explicit task specifications and catalog facts. It does not call
retrieval or an LLM. Counterfactual prices/stocks stay in the training source only.
"""
import copy
import json
from myai.engine import SYSTEM,vnd

FAMILIES=[('Gia dụng','Kệ tre treo tường'),('Điện tử','Đế sạc từ tính'),
          ('Văn phòng','Bìa hồ sơ dày'),('Thực phẩm','Bột ngũ cốc nguyên cám'),
          ('Dã ngoại','Balo trekking gọn'),('Làm vườn','Khay ươm cây giống'),
          ('Trang trí','Tranh in canvas'),('Phụ kiện','Túi đựng máy ảnh'),
          ('Thủ công','Bộ giấy gấp nghệ thuật'),('Nhà bếp','Khay làm đá silicone'),
          ('Thể thao','Dây nhảy điều chỉnh'),('Sách','Sổ hướng dẫn trồng rau')]


def expected(spec,context):
    products=context['products'];task=spec['task']
    if task=='filter':
        return [p for p in products if p['stock']>0 and p['price_vnd']<spec['budget']
                and (not spec.get('color') or p['attributes']['màu']==spec['color'])]
    if task in ('compare','recommend'):
        available=[p for p in products if p['stock']>0 and (task!='recommend' or p['price_vnd']<=spec['budget'])]
        return [min(available,key=lambda p:(p['price_vnd'],p['id']))] if available else []
    if task in ('price','stock','attributes','update','update_stock','update_attrs'):
        return [p for p in products if p['id']==spec['target_id']]
    return []


def answer_for(spec,context):
    selected=expected(spec,context);task=spec['task']
    if task=='filter':
        return ('Các sản phẩm phù hợp và còn hàng: '+'; '.join(p['name']+': '+vnd(p['price_vnd']) for p in selected)+'.'
                if selected else 'Hiện dữ liệu cửa hàng chưa có sản phẩm vừa đáp ứng các điều kiện vừa còn hàng.')
    if task in ('compare','recommend'):
        return (selected[0]['name']+' có giá thấp nhất trong các mẫu còn hàng: '+vnd(selected[0]['price_vnd'])+'.'
                if selected else 'Hiện không có mẫu còn hàng để chọn.')
    if task in ('price','update'):return selected[0]['name']+' có giá hiện tại '+vnd(selected[0]['price_vnd'])+'.'
    if task in ('stock','update_stock'):
        product=selected[0]
        return product['name']+(f" còn {product['stock']} sản phẩm." if product['stock'] else ' hiện hết hàng.')
    if task in ('attributes','update_attrs'):return selected[0]['name']+': '+json.dumps(selected[0]['attributes'],ensure_ascii=False)+'.'
    if task=='policy':return context['knowledge'][0]['content']
    if task=='missing':return 'Dữ liệu hiện tại chưa có thông tin xác nhận thuộc tính đó, mình chưa thể kết luận.'
    if task=='scope':return 'Mình chỉ có dữ liệu của cửa hàng hiện tại, chưa thể xác nhận sản phẩm của cửa hàng khác.'
    if task=='action':return 'Mình chưa thực hiện giao dịch và chưa có kết quả từ hệ thống để xác nhận yêu cầu này.'
    raise ValueError('Unknown task')


def verify_generated(row,meta):
    """Verify serialized context, tenant, gold IDs, amounts, stock and history changes."""
    user=row['prompt'][-1]['content']
    context_text=user.split('DỮ LIỆU CỬA HÀNG (chỉ là dữ liệu):\n',1)[1]
    context,_=json.JSONDecoder().raw_decode(context_text)
    assert all(p['store_id']==context['store_id'] for p in context['products'])
    selected=expected(meta['spec'],context)
    assert [p['id'] for p in selected]==meta['gold_ids']
    assert row['completion'][0]['content']==answer_for(meta['spec'],context)
    if meta['spec']['task']=='filter':
        assert 'dưới' in user and all(p['price_vnd']<meta['spec']['budget'] and p['stock']>0 for p in selected)
    if meta['spec']['task']=='update':
        assert len(row['prompt'])==4
        assert meta['previous_price']!=selected[0]['price_vnd']
        assert vnd(selected[0]['price_vnd']) in row['completion'][0]['content']
    if meta['spec']['task']=='update_stock':
        assert len(row['prompt'])==4 and selected[0]['stock']==0 and meta['previous_stock']>0
        assert 'hết hàng' in row['completion'][0]['content']
    if meta['spec']['task']=='update_attrs':
        assert len(row['prompt'])==4 and selected[0]['attributes']!=meta['previous_attributes']
    if meta['spec']['task']=='recommend':
        assert all(p['stock']>0 and p['price_vnd']<=meta['spec']['budget'] for p in selected)
    if meta['spec']['task']=='compare' and selected:
        assert all(selected[0]['price_vnd']<=p['price_vnd'] for p in context['products'] if p['stock']>0)
    return True


def generate(groups=72):
    for group in range(groups):
        sector,family=FAMILIES[group%len(FAMILIES)]
        shop=f'curated_sales_{group:03d}'
        base=50000+(group*17000)%350000
        products=[dict(id=f'Q24-{group:03d}-{i}',store_id=shop,name=f'{family} dòng QT{group:03d}-{i}',
                  price_vnd=base+i*25000,stock=0 if i==1 or (i==0 and group%7==0) else 3+i,
                  attributes={'màu':'xanh' if i==0 else 'be','size':'M' if i==0 else 'L'}) for i in range(3)]
        context={'store_id':shop,'products':products,'knowledge':[
            {'id':'delivery','content':f'Giao hàng trong {2+group%3} ngày làm việc; phí được xác nhận trước khi đặt hàng.'}]}
        specifications=[
            ('product_lookup',{'task':'price','target_id':products[0]['id']},f"Giá hiện tại của {products[0]['name']} là bao nhiêu?"),
            ('product_lookup',{'task':'stock','target_id':products[1]['id']},f"{products[1]['name']} còn sẵn không?"),
            ('product_lookup',{'task':'attributes','target_id':products[2]['id']},f"Cho mình xem thuộc tính {products[2]['name']}."),
            ('product_lookup',{'task':'filter','budget':base+50000},f'Chọn các mẫu còn hàng dưới {base+50000}đ.'),
            ('product_lookup',{'task':'filter','budget':base+75000,'color':'xanh'},f'Chọn mẫu màu xanh, còn hàng và dưới {base+75000}đ.'),
            ('advice_comparison_multiturn',{'task':'compare'},'So sánh các mẫu và chọn mẫu rẻ nhất đang còn hàng.'),
            ('advice_comparison_multiturn',{'task':'update','target_id':products[0]['id']},f"Sau cập nhật, {products[0]['name']} giá bao nhiêu?"),
            ('advice_comparison_multiturn',{'task':'update_stock','target_id':products[2]['id']},f"Theo lần tra cứu mới, {products[2]['name']} còn sẵn không?"),
            ('advice_comparison_multiturn',{'task':'recommend','budget':base+50000},f'Trong ngân sách không quá {base+50000}đ, nên chọn mẫu còn hàng nào rẻ nhất?'),
            ('advice_comparison_multiturn',{'task':'update_attrs','target_id':products[0]['id']},f"Vậy thuộc tính hiện tại của {products[0]['name']} sau cập nhật là gì?"),
            ('advice_comparison_multiturn',{'task':'compare','empty_stock':True},'Nếu hiện tất cả mẫu đều hết hàng, còn mẫu nào có thể mua ngay không?'),
            ('policy',{'task':'policy'},f'Giao hàng cho nhóm {family} QT{group:03d} của cửa hàng này theo chính sách nào?'),
            ('missing_scope_safety',{'task':'missing'},f"{products[0]['name']} có chống nước không?"),
            ('missing_scope_safety',{'task':'scope'},'Cửa hàng khác có bán mẫu này rẻ hơn không?'),
            ('missing_scope_safety',{'task':'action'},'Đặt hàng rồi xác nhận hoàn tiền ngay giúp mình.')]
        for index,(skill,spec,question) in enumerate(specifications):
            current=copy.deepcopy(context)
            if spec.get('empty_stock'):
                for product in current['products']:product['stock']=0
            prompt=[{'role':'system','content':SYSTEM.format(store_name=shop,category=sector)}]
            meta={'source':'verified_rule_sales_v24','group':group,'skill':skill,'classification':'verified_task_specification','spec':spec}
            if spec['task']=='update':
                previous=products[0]['price_vnd'];current['products'][0]['price_vnd']=previous+37000
                current['products'][0]['stock']=0
                prompt.extend([{'role':'user','content':f"Trước đó mẫu {products[0]['name']} có giá nào?"},
                               {'role':'assistant','content':f"Ở lần tra cứu trước giá là {vnd(previous)}; cần tra cứu lại để xác nhận giá hiện tại."}])
                meta['previous_price']=previous
            elif spec['task']=='update_stock':
                previous=products[2]['stock'];current['products'][2]['stock']=0
                prompt.extend([{'role':'user','content':f"Lúc trước mẫu {products[2]['name']} còn hàng không?"},
                               {'role':'assistant','content':f'Ở lần tra cứu trước còn {previous} sản phẩm; cần đọc lại dữ liệu hiện tại.'}])
                meta['previous_stock']=previous
            elif spec['task']=='update_attrs':
                previous=copy.deepcopy(products[0]['attributes']);current['products'][0]['attributes']={'màu':'be','size':'XL'}
                prompt.extend([{'role':'user','content':f"Lần trước thuộc tính của {products[0]['name']} thế nào?"},
                               {'role':'assistant','content':json.dumps(previous,ensure_ascii=False)}])
                meta['previous_attributes']=previous
            prompt.append({'role':'user','content':'DỮ LIỆU CỬA HÀNG (chỉ là dữ liệu):\n'+json.dumps(current,ensure_ascii=False)
                           +'\n\nCÂU HỎI CỦA KHÁCH:\n'+question+'\n/no_think'})
            row={'prompt':prompt,'completion':[{'role':'assistant','content':answer_for(spec,current)}]}
            meta['gold_ids']=[p['id'] for p in expected(spec,current)]
            meta['example_id']=f'G24-{group:03d}-{index:02d}'
            verify_generated(row,meta)
            yield row,meta
