"""Tenant-isolated lexical search with strict, current catalog constraints."""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from .db import get_products, get_knowledge
from .normalization import (normalize_text, normalize_query, decimal_number, equivalent_value,
                            wireless_evidence, category_constraints, quantity_constraints, has_phrase)


def normalize(text):
    return normalize_text(text)


STOP = set(('shop cua hang ben minh co la cho xem em anh chi ban mot cai nhung san pham '
            'nao gia bao nhieu khong duoc voi va de o a hay gi da con thay mon goi y tu van '
            'lua chon danh sach menu muon tim mua can xin nhe nha hoi hien dang tien '
            'het san luong tinh so nay the giup dac diem thong tin mo ta '
            'dung roi doi moi nhap bay gio du lieu').split())
COLORS = {'den', 'trang', 'xanh', 'do', 'be', 'hong', 'vang', 'xam', 'nau', 'tim', 'kem'}
COLOR_PATTERN = ('(?:' + '|'.join(sorted(COLORS)) + ')'
                 + r'(?:\s+(?:do|nhat|dam|navy|reu|la|duong|kem|tro|phan|bien|ngoc))?')
NUMBER = r'\d+(?:[.,]\d+)*'
UNIT = r'(?:trieu|tr|nghin|ngan|k|dong|vnd|d|₫)'
AMOUNT = rf'({NUMBER})\s*({UNIT})?(?:\b|(?<=₫))'


def tokens(text):
    return {word for word in re.findall(r'[a-z0-9]+', normalize(text)) if word not in STOP}


def money_value(number, unit=None):
    if unit in ('trieu', 'tr', 'nghin', 'ngan', 'k'):
        factor = 1_000_000 if unit in ('trieu', 'tr') else 1000
        try:
            amount=decimal_number(number)*factor
            if amount!=amount.to_integral_value():raise ValueError('Fractional VND is not supported')
            return int(amount)
        except (InvalidOperation,ValueError) as error:
            raise ValueError('Invalid currency amount') from error
    amount=decimal_number(number)
    if amount!=amount.to_integral_value():raise ValueError('Fractional VND is not supported')
    return int(amount)


def price_constraints(query):
    """Return inclusive VND bounds and text without recognized price clauses."""
    text = normalize_query(query)
    def expand_millions(match):
        fraction=match[2]
        if len(fraction)==2:raise ValueError('Ambiguous shorthand price; specify full VND amount')
        value=Decimal(match[1])*1_000_000+Decimal(fraction)*1_000_000/(10**len(fraction))
        return str(int(value))+' dong'
    text=re.sub(r'(?<!\w)(\d+)\s*(?:trieu|tr)\s*(\d{1,3})(?!\w)',expand_millions,text)
    lower = upper = None
    interval = re.search(rf'(?<!\w)(?:(?:tu|gia|khoang)\s+)?{AMOUNT}\s*(?:den|toi|-)\s*{AMOUNT}', text)
    if interval:
        first, first_unit, last, last_unit = interval.groups()
        lower = money_value(first, first_unit or last_unit)
        upper = money_value(last, last_unit or first_unit)
        text = text[:interval.start()] + ' ' + text[interval.end():]
    pattern = rf'(?<!\w)(khong vuot qua|khong qua|ngan sach|toi da|duoi|nho hon|khong duoi|it nhat|toi thieu|tren|lon hon|<=|>=|<|>)\s*{AMOUNT}'
    def remove_bound(match):
        nonlocal lower, upper
        operator, number, unit = match.groups()
        value = money_value(number, unit)
        if operator in ('khong vuot qua', 'khong qua', 'ngan sach', 'toi da', 'duoi', 'nho hon', '<=', '<'):
            value -= operator in ('duoi', 'nho hon', '<')
            upper = value if upper is None else min(upper, value)
        else:
            value += operator in ('tren', 'lon hon', '>')
            lower = value if lower is None else max(lower, value)
        return ' '
    text = re.sub(pattern, remove_bound, text)
    # A suggested price in a factual question must not filter out the real price.
    text = re.sub(rf'(?<!\w){NUMBER}\s*{UNIT}(?:\b|(?<=₫))', ' ', text)
    return lower, upper, text


def maximum_price(query):
    """Compatibility helper: return the stated ceiling, before strict comparison."""
    _, upper, _ = price_constraints(query)
    if upper is not None and re.search(r'\b(?:duoi|nho hon)\b|(?<![<>=])<(?![=])', normalize(query)):
        return upper + 1
    return upper


def wants_non_spicy(query):
    return bool(re.search(r'\bkhong (?:an )?cay\b', normalize(query)))


def wanted_size(query):
    match = re.search(r'\b(?:size|sz|kich co)\s*(xxxl|xxl|xl|xs|s|m|l|\d{2})\b', normalize(query))
    return match.group(1).upper() if match else None


def wanted_color(query):
    match = re.search(r'\bmau\s+(' + COLOR_PATTERN + r')\b', normalize(query))
    return match.group(1) if match else None


def field_values(attrs, names):
    return [value for key, values in attrs.items() if normalize(key) in names
            for value in (values if isinstance(values, list) else [values])]


def attribute_key(key):
    normalized = normalize(key).strip()
    aliases = {'mau':'color', 'mau sac':'color', 'kich co':'size', 'co':'size',
               'thuong hieu':'brand', 'chat lieu':'material', 'dung tich':'capacity',
               'chieu dai':'length','khoi luong':'mass','can nang':'mass','cong suat':'power',
               'dung luong':'storage','duong kinh':'diameter'}
    return aliases.get(normalized, normalized)


@dataclass
class SearchFilters:
    min_price: int | None = None
    max_price: int | None = None
    in_stock: bool | None = None
    attributes: dict = field(default_factory=dict)

    def __post_init__(self):
        for value in (self.min_price, self.max_price):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Price bounds must be nonnegative integers in VND')
        if self.min_price is not None and self.max_price is not None and self.min_price > self.max_price:
            raise ValueError('Minimum price exceeds maximum price')
        if self.in_stock is not None and type(self.in_stock) is not bool:
            raise ValueError('in_stock must be boolean')
        if not isinstance(self.attributes, dict):
            raise ValueError('attributes must be an object')


def _attribute_matches(actual, requested):
    actual = actual if isinstance(actual, list) else [actual]
    requested = requested if isinstance(requested, list) else [requested]
    return bool(requested) and all(any(equivalent_value(value,want) for value in actual) for want in requested)


def search_products(conn, store_id, query, limit=6, filters=None):
    if not 1 <= limit <= 100:
        raise ValueError('Product limit must be between 1 and 100')
    filters = filters or SearchFilters()
    try:
        lower, upper, text = price_constraints(query)
    except ValueError:
        return []
    text = re.sub(r'\btinh trang\b', ' ', text)
    text = re.sub(r'\b(?:vui long|cho (?:toi|to)|giup (?:toi|to)|(?:toi|to) (?:muon|can|tim|mua|xem))\b', ' ', text)
    text,quantities=quantity_constraints(text)
    size = wanted_size(text)
    excluded_color_match=re.search(r'\bkhong\s+(?:lay\s+|chon\s+)?mau\s+('+COLOR_PATTERN+r')\b',text)
    excluded_color=excluded_color_match[1] if excluded_color_match else None
    if excluded_color_match:text=text[:excluded_color_match.start()]+' '+text[excluded_color_match.end():]
    color = wanted_color(text)
    non_spicy = wants_non_spicy(text)
    text = re.sub(r'\b(?:size|sz|kich co)\s*(?:xxxl|xxl|xl|xs|s|m|l|\d{2})\b', ' ', text)
    text = re.sub(r'\bmau\s+(' + COLOR_PATTERN + r')\b', ' ', text)
    text = re.sub(r'\bkhong (?:an )?cay\b', ' ', text)
    wireless=bool(re.search(r'\b(?:khong day|wireless)\b',text))
    text=re.sub(r'\b(?:khong day|wireless)\b',' ',text)
    text,categories=category_constraints(text)
    # Availability questions retain sold-out named products as evidence.
    stock = None
    if re.search(r'\bkhong con (?:hang|san)\b', text):
        stock = False
    elif re.search(r'\bhet hang\b', text) and not re.search(r'\b(?:khong|chua) het hang\b', text):
        stock = False
    elif re.search(r'\b(?:con hang|con san|co san|chua het hang|khong het hang)\b', text) and not re.search(r'\b(?:con hang|con san|co san)\s*(?:khong|chua)\b|\b(?:con|co san)\s+.+\s+khong\b', text):
        stock = True
    text=re.sub(r'\b(?:khong con (?:hang|san)|chua het hang|khong het hang|con san|co san|con hang|het hang)\b',' ',text)
    # Unsupported mandatory negation fails closed; a trailing availability question is fine.
    if re.search(r'\bkhong\s+(?!a\b|nhe\b|shop\b|vay\b)[a-z0-9]+',text):return []
    text = re.sub(r'\b\d+\s*(?:goi|cai|san pham)\b', ' ', text)
    query_words = tokens(text)
    lower = max((value for value in (lower, filters.min_price) if value is not None), default=None)
    upper = min((value for value in (upper, filters.max_price) if value is not None), default=None)
    if lower is not None and upper is not None and lower > upper:
        return []
    if stock is not None and filters.in_stock is not None and stock != filters.in_stock:
        return []
    stock = filters.in_stock if filters.in_stock is not None else stock
    has_request = bool(query_words or lower is not None or upper is not None or size or color or non_spicy or excluded_color or wireless or categories or quantities
                       or stock is not None or filters != SearchFilters()
                       or re.search(r'\b(?:menu|danh sach|goi y|ban gi|san pham|mon gi)\b', normalize(query)))
    ranked = []
    # Read all tenant candidates: a matching SKU may sort after the first 2,000.
    for product in get_products(conn, store_id, limit=None, min_price=lower, max_price=upper, in_stock=stock):
        attrs = product['attributes']
        if wireless and not wireless_evidence(product):continue
        catalog_text=normalize(product['name']+' '+' '.join(str(value) for value in attrs.values()))
        if any(not any(has_phrase(catalog_text,phrase) for phrase in category['catalog_phrases']) for category in categories):continue
        normalized_attrs = {}
        for key, value in attrs.items():
            values = value if isinstance(value, list) else [value]
            normalized_attrs.setdefault(attribute_key(key), []).extend(values)
        if any(not _attribute_matches(normalized_attrs.get(attribute_key(key), []), value)
               for key, value in filters.attributes.items()):
            continue
        if any(not _attribute_matches(normalized_attrs.get(key,[]),value) for key,value in quantities):continue
        if size and not _attribute_matches(field_values(attrs, {'size', 'kich thuoc', 'co', 'kich co'}), size):
            continue
        if color and not any(normalize(value) == color or normalize(value).startswith(color + ' ')
                             for value in field_values(attrs, {'mau', 'mau sac', 'color'})):
            continue
        if excluded_color:
            colors=field_values(attrs,{'mau','mau sac','color'})
            if not colors or any(normalize(value)==excluded_color or normalize(value).startswith(excluded_color+' ') for value in colors):continue
        details = normalize(product['description'] + ' ' + ' '.join(str(value) for value in attrs.values()))
        if non_spicy and 'khong cay' not in details:
            continue
        name_words = tokens(product['name'])
        detail_words = tokens(details)
        id_words = tokens(product['id'])
        # Filters never authorize unrelated products. Unknown keywords fail closed.
        if query_words and not query_words <= name_words | detail_words | id_words:
            continue
        if not has_request:
            continue
        score = len(query_words & name_words) * 5 + len(query_words & detail_words) * 2
        ranked.append((score, product))
    ranked.sort(key=lambda pair: (-pair[0], normalize(pair[1]['name']), pair[1]['id']))
    # A fully named SKU takes precedence over another item sharing broad keywords.
    exact_names = [pair for pair in ranked if re.search(r'(?<!\w)' + re.escape(normalize(pair[1]['name'])) + r'(?!\w)', normalize(query))]
    if exact_names:
        ranked = exact_names
    return [product for _, product in ranked[:limit]]


def retrieve(conn, store_id, query, product_limit=6, knowledge_limit=3, filters=None):
    products = search_products(conn, store_id, query, product_limit, filters)
    query_words = tokens(query)
    ranked = []
    for doc in get_knowledge(conn, store_id):
        title_words = tokens(doc['title'])
        overlap = query_words & tokens(doc['title'] + ' ' + doc['content'])
        return_policy = ('doi tra' in normalize(doc['title'])
                         and bool(re.search(r'\b(?:doi size|doi hang|doi tra|tra hang)\b', normalize(query))))
        if query_words & title_words or len(overlap) >= 2 or return_policy:
            ranked.append((len(query_words & title_words) * 3 + len(overlap), doc))
    ranked.sort(key=lambda pair: (-pair[0], pair[1]['id']))
    return products, [doc for _, doc in ranked[:knowledge_limit]]
