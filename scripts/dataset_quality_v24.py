"""Explainable dataset grouping and heuristic skill classification, not semantic certification."""
from collections import defaultdict
import hashlib
import re
from scripts.curate_candidate import question_text,question_key,CONTEXT,review_reasons
from MyAI_Quality_Gate_v2_1.quality_gate import user_string,assistant_string
from myai.normalization import normalize_text
from myai.grounding import COMPLETED_ACTION

SKILLS=('product_lookup','advice_comparison_multiturn','policy','customer_support','missing_scope_safety')


def estimated_skill(row):
    query=normalize_text(question_text(row));answer=normalize_text(assistant_string(row))
    structured=bool(CONTEXT.search(user_string(row)))
    if re.search(r'bo qua|bia gia|khong co trong|cua hang khac|chua co (?:du lieu|thong tin)|mat khau|otp|cvv',query+' '+answer):
        return 'missing_scope_safety'
    if re.search(r'so sanh|re hon|chenh lech|phan van|giua .* voi ',query) or (structured and len(row['prompt'])>2):
        return 'advice_comparison_multiturn'
    if re.search(r'chinh sach|giao hang|doi tra|doi size|phi ship|thanh toan|bao hanh',query):return 'policy'
    if structured:return 'product_lookup'
    if re.search(r'gia|ton kho|con hang|mau|kich thuoc|tim san pham|goi y',query):return 'product_lookup'
    return 'customer_support'


def extra_risks(row):
    risks=review_reasons(row)
    user=user_string(row);answer=assistant_string(row)
    if COMPLETED_ACTION.search(normalize_text(answer)):risks.append('executed_action_outside_catalog_backend')
    if not CONTEXT.search(user):
        context=re.split(r'CÂU HỎI CỦA KHÁCH:|\nKHÁCH:',user)[0]
        for claim in re.findall(r'\b\d+(?:[.,]\d+)?\s*(?:%|ngày|giờ|phút)',answer):
            if claim not in context:risks.append('policy_or_time_number_without_context');break
    return sorted(set(risks))


def answer_template(row):
    text=normalize_text(assistant_string(row))
    text=re.sub(r'\b[a-z]*\d+[a-z0-9.-]*\b','[identifier]',text)
    return re.sub(r'\s+',' ',text).strip()


def question_shingles(row):
    text=normalize_text(question_key(row));words=text.split()
    if len(words)<8:return set(),frozenset()
    shingles={' '.join(words[i:i+3]) for i in range(len(words)-2)}
    return shingles,frozenset(re.findall(r'\b\d+(?:[.,]\d+)?\b',text))


class NearQuestionIndex:
    """Exact Jaccard over trigram candidates; numbers must agree. No embedding claims."""
    def __init__(self):
        self.entries=[];self.postings=defaultdict(set)

    def add(self,row,reference):
        shingles,numbers=question_shingles(row)
        if not shingles:return
        index=len(self.entries);self.entries.append((shingles,numbers,reference))
        for shingle in shingles:self.postings[shingle].add(index)

    def match(self,row,threshold=.82):
        shingles,numbers=question_shingles(row)
        if not shingles:return None
        candidates=set()
        # All shared trigrams are considered: no approximate LSH recall claim.
        for shingle in shingles:candidates.update(self.postings.get(shingle,()))
        for index in sorted(candidates):
            other,other_numbers,reference=self.entries[index]
            if numbers!=other_numbers:continue
            score=len(shingles&other)/len(shingles|other)
            if score>=threshold:return {'reference':reference,'jaccard':round(score,6)}
        return None
