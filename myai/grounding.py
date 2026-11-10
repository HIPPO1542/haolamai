"""Conservative checks for facts the catalog-only backend can actually support."""
import re
from .normalization import normalize_text

COMPLETED_ACTION=re.compile(
    r'\b(?:da|vua)\s+(?:dat hang|tao don|len don|chot don|dat lich|giu cho|hoan tien|huy don|'
    r'xac nhan (?:don|lich|thanh toan)|chuyen (?:ban|anh|chi|em|yeu cau|cuoc hoi thoai))\b|'
    r'\b(?:dang|se)\s+(?:chuyen (?:ban|anh|chi|yeu cau)|ket noi (?:ban|anh|chi))\b|'
    r'\b(?:dat hang|dat lich|hoan tien)\s+thanh cong\b')


def unsupported_catalog_claim(answer,products):
    text=normalize_text(answer)
    # This backend does not execute orders, refunds, bookings or handoffs. User
    # text and retrieved policy text cannot confer evidence of an executed action.
    if COMPLETED_ACTION.search(text):return 'unverified_backend_action'
    if len(products)==1:
        stock=products[0]['stock']
        quantities=[int(number) for number in re.findall(r'\b(?:con|ton|ton kho)\s+(\d+)\s+(?:san pham|goi|cai|chiec)\b',text)]
        if any(number!=stock for number in quantities):return 'unsupported_stock_claim'
        positive=re.sub(r'\b(?:khong|chua)\s+(?:con hang|het hang)\b',' ',text)
        if stock==0 and re.search(r'\bcon hang\b',positive):return 'unsupported_stock_claim'
        if stock>0 and re.search(r'\bhet hang\b',positive):return 'unsupported_stock_claim'
    return None
