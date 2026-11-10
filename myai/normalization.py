"""Deterministic text, measurement and connection equivalence from catalog facts."""
from decimal import Decimal, InvalidOperation
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata


def normalize_text(text):
    text=unicodedata.normalize('NFD',str(text).lower())
    return ''.join(char for char in text if unicodedata.category(char)!='Mn').replace('đ','d')


@lru_cache(maxsize=1)
def lexicon():
    return json.loads(Path(__file__).with_name('search_lexicon.json').read_text(encoding='utf-8'))


def normalize_query(text):
    normalized=normalize_text(text).replace('–','-').replace('—','-').replace('≤','<=').replace('≥','>=')
    for source,target in sorted(lexicon()['query_replacements'].items(),key=lambda item:-len(item[0])):
        normalized=re.sub(r'(?<![\w-])'+re.escape(source)+r'(?![\w-])',target,normalized)
    return normalized


def decimal_number(text):
    text=str(text).strip()
    if re.fullmatch(r'[1-9]\d{0,2}(?:[.,]\d{3})+',text):
        text=text.replace('.','').replace(',','')
    else:
        text=text.replace(',','.')
    try:return Decimal(text)
    except InvalidOperation as error:raise ValueError('Invalid decimal amount') from error


MEASUREMENTS={
    'ml':('volume',Decimal('1')), 'mililit':('volume',Decimal('1')),
    'cl':('volume',Decimal('10')), 'dl':('volume',Decimal('100')),
    'l':('volume',Decimal('1000')), 'lit':('volume',Decimal('1000')),
    'mg':('mass',Decimal('.001')), 'g':('mass',Decimal('1')), 'gram':('mass',Decimal('1')),
    'kg':('mass',Decimal('1000')), 'kilogram':('mass',Decimal('1000')),
    'mm':('length',Decimal('1')), 'cm':('length',Decimal('10')), 'dm':('length',Decimal('100')),
    'm':('length',Decimal('1000')), 'met':('length',Decimal('1000')),
    'w':('power',Decimal('1')), 'kw':('power',Decimal('1000')),
    'mb':('storage',Decimal('1000000')), 'gb':('storage',Decimal('1000000000')),
    'tb':('storage',Decimal('1000000000000')), 'gib':('storage',Decimal(2**30))
}


def measurement(value):
    match=re.fullmatch(r'\s*(\d+(?:[.,]\d+)*)\s*([a-z]+)\s*',normalize_text(value))
    if not match or match[2] not in MEASUREMENTS:return None
    dimension,factor=MEASUREMENTS[match[2]]
    try:return dimension,decimal_number(match[1])*factor
    except ValueError:return None


def equivalent_value(actual,requested):
    first,second=measurement(actual),measurement(requested)
    if first is not None and second is not None:return first==second
    return normalize_text(actual).strip()==normalize_text(requested).strip()


def has_phrase(text,phrase):
    return bool(re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',normalize_text(text)))


def wireless_evidence(product):
    """Wireless is accepted only from explicit connection attributes or product name."""
    names={'ket noi','connectivity','connection','wireless','chuan ket noi'}
    values=[]
    for key,value in product['attributes'].items():
        if normalize_text(key) in names:values.extend(value if isinstance(value,list) else [value])
    values.append(product['name'])
    for value in values:
        text=normalize_text(value)
        if re.search(r'\b(?:khong|no|without)\s+(?:co\s+)?(?:bluetooth|wifi|wi-fi|wireless)\b',text):continue
        if re.search(r'\b(?:bluetooth|bt(?:\s*\d+(?:\.\d+)?)?|wi-?fi|wireless|khong day|2[.,]4\s*ghz)\b',text):return True
    return False


def category_constraints(text):
    categories=[]
    for category in lexicon()['categories']:
        for phrase in sorted(category['query_phrases'],key=len,reverse=True):
            if has_phrase(text,phrase):
                text=re.sub(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',' ',text)
                if category not in categories:categories.append(category)
    return text,categories


def quantity_constraints(text):
    """Extract explicit attribute/value phrases, never infer a missing DB field."""
    aliases={'dung tich':'capacity','suc chua':'capacity','chieu dai':'length','dai':'length',
             'khoi luong':'mass','can nang':'mass','cong suat':'power','dung luong':'storage',
             'duong kinh':'diameter'}
    units='|'.join(sorted(MEASUREMENTS,key=len,reverse=True))
    pattern=r'\b('+ '|'.join(sorted(aliases,key=len,reverse=True))+r')\s+(\d+(?:[.,]\d+)*\s*(?:'+units+r'))\b'
    constraints=[]
    def remove(match):
        constraints.append((aliases[match[1]],match[2]));return ' '
    return re.sub(pattern,remove,text),constraints
