"""Build a conservative versioned candidate; preserve held-out test bytes.

Quarantine is reversible and references source lines. No candidate is automatically
approved for training. Review exports contain redacted previews, not raw PII.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import re
import unicodedata

from scripts.audit_datasets import rows
from scripts.training_data_guard import validate_training_inputs
from MyAI_Quality_Gate_v2_1.quality_gate import rule_flags, user_string, assistant_string, PII
from myai.engine import currency_values
from myai.retrieval import normalize, price_constraints

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = re.compile(r'DỮ LIỆU CỬA HÀNG(?: HIỆN TẠI)? \(chỉ là dữ liệu\):')


def question_text(row):
    user = user_string(row)
    question = re.split(r'CÂU HỎI CỦA KHÁCH:|\nKHÁCH:', user)[-1]
    return question.split('KẾT QUẢ HỆ THỐNG')[0].replace('/no_think', '').strip()


def question_key(row):
    question = unicodedata.normalize('NFKC', question_text(row)).casefold()
    return re.sub(r'[^\w]+', ' ', question).strip()


def source_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def review_reasons(row):
    high, medium = rule_flags(row)
    reasons = set(high + medium)
    user, answer = user_string(row), assistant_string(row)
    marker = CONTEXT.search(user)
    facts = None
    if marker:
        try:
            facts, _ = json.JSONDecoder().raw_decode(user[marker.end():].lstrip())
            if not isinstance(facts, dict):
                reasons.add('invalid_context_object')
                facts = None
        except ValueError:
            reasons.add('invalid_context_json')
    try:
        answer_prices = set(currency_values(answer))
    except ValueError:
        reasons.add('malformed_answer_price')
        answer_prices = set()
    if facts is not None:
        prices = {product['price_vnd'] for product in facts.get('products', [])}
        policy_prices = set(currency_values(' '.join(doc.get('content', '') for doc in facts.get('knowledge', []))))
        extra_prices = answer_prices - prices - policy_prices
        refutation = ('chưa thấy xác nhận mức giá' in answer
                      and extra_prices <= set(currency_values(question_text(row))))
        if extra_prices and not refutation:
            reasons.add('answer_price_not_in_facts')
        lower, upper, _ = price_constraints(question_text(row))
        for product in facts.get('products', []):
            if product['name'].casefold() not in answer.casefold():
                continue
            if ((lower is not None and product['price_vnd'] < lower)
                    or (upper is not None and product['price_vnd'] > upper)):
                reasons.add('product_outside_requested_price_range')
            if len(facts.get('products', [])) == 1:
                amounts = [int(value) for value in re.findall(r'\b(?:ton|con)\s+(\d+)\s+(?:san pham|goi|cai)\b', normalize(answer))]
                if any(value != product['stock'] for value in amounts):
                    reasons.add('answer_stock_not_in_facts')
    else:
        # Customer-supplied numbers and previous assistant turns are not verified facts.
        context = re.split(r'CÂU HỎI CỦA KHÁCH:|\nKHÁCH:', user)[0]
        store_context = context.startswith('THÔNG TIN CỬA HÀNG')
        if answer_prices and (not store_context or not answer_prices <= set(currency_values(context))):
            reasons.add('numeric_claim_without_verified_context')
        normalized_answer = normalize(answer)
        asserted_state = re.search(r'\b(?:don hang|san pham|lich hen).{0,60}\b(?:dang duoc giao|da duoc xac nhan|con hang|het hang|da thanh toan)\b', normalized_answer)
        if asserted_state and 'KẾT QUẢ HỆ THỐNG' not in user:
            reasons.add('state_claim_without_system_result')
        if (re.search(r'giao sai|giao thieu|hu hong|rach|sut chi|doi hang', normalize(question_text(row)))
                and re.search(r'van de thanh toan|doi soat thanh toan', normalized_answer)
                and 'hoan tien' not in normalize(question_text(row))):
            reasons.add('likely_question_answer_topic_mismatch')
    return sorted(reasons)


def write_rows(path, records):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False)+'\n')


def build(source, output):
    if output.exists():
        raise ValueError('Output already exists; no overwrite allowed')
    source_files = [source/(split+'.jsonl') for split in ('train', 'validation', 'test_external', 'myai_eval_cases')]
    before = {path.name: source_hash(path) for path in source_files}
    original = {split: list(rows(source/(split+'.jsonl'))) for split in ('train', 'validation', 'test_external')}
    output.mkdir(parents=True)
    accepted = {'test_external': [row for _, row in original['test_external']]}
    blocked_keys = {question_key(row) for row in accepted['test_external']}
    quarantine = []
    decisions = []
    reason_counts = Counter()
    for split in ('validation', 'train'):
        accepted[split] = []
        for line, row in original[split]:
            reasons = review_reasons(row)
            key = question_key(row)
            if key in blocked_keys:
                reasons.append('question_group_reserved_for_heldout')
            decision = {'split': split, 'source_line': line,
                'record_sha256': hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                'status': 'QUARANTINED' if reasons else 'AUTO_ACCEPTED', 'reasons': sorted(set(reasons))}
            decisions.append(decision)
            if reasons:
                reason_counts.update(set(reasons))
                quarantine.append(dict(decision,
                    question_preview=PII.sub('[REDACTED]', question_text(row))[:500],
                    answer_preview=PII.sub('[REDACTED]', assistant_string(row))[:600]))
            else:
                accepted[split].append(row)
        if split == 'validation':
            blocked_keys.update(question_key(row) for row in accepted[split])
    # Preserve both evaluation sources verbatim; never curate or repurpose test.
    (output/'test_external.jsonl').write_bytes((source/'test_external.jsonl').read_bytes())
    (output/'myai_eval_cases.jsonl').write_bytes((source/'myai_eval_cases.jsonl').read_bytes())
    for split in ('train', 'validation'):
        write_rows(output/(split+'.jsonl'), accepted[split])
    write_rows(output/'decisions.jsonl', decisions)
    write_rows(output/'review_queue_redacted.jsonl', quarantine)
    sets = {split: {question_key(row) for row in records} for split, records in accepted.items()}
    overlap = {a+'_vs_'+b: len(sets[a] & sets[b]) for a,b in itertools.combinations(sets, 2)}
    validate_training_inputs(output/'train.jsonl', output/'validation.jsonl', output/'test_external.jsonl')
    after = {path.name: source_hash(path) for path in source_files}
    if before != after or any(overlap.values()):
        raise RuntimeError('Source changed or held-out question overlap remains')
    heldout_flags = Counter(reason for _, row in original['test_external'] for reason in review_reasons(row))
    report = {'original_counts': {split: len(records) for split, records in original.items()},
        'candidate_counts': {split: len(records) for split, records in accepted.items()},
        'independent_benchmark': len(list(rows(source/'myai_eval_cases.jsonl'))),
        'quarantined_rows': len(quarantine), 'quarantine_reasons': dict(reason_counts),
        'question_group_overlap': overlap, 'heldout_review_flags_test_unchanged': dict(heldout_flags),
        'input_sha256': before, 'source_unchanged': before == after,
        'test_copied_byte_for_byte': source_hash(output/'test_external.jsonl') == before['test_external.jsonl'],
        'ready_for_training': False,
        'policy': ['Conservative automatic curation; quarantine is reversible via source line references.',
            'Test has priority, then cleaned validation, then train. No heldout row is moved to train.',
            'Long-answer flags are quarantined rather than silently approved.',
            'No semantic/privacy or rights certification; tokenizer/model evaluation still required.']}
    (output/'audit_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='outputs/verified_v2_2/review_candidate')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = (ROOT/args.input).resolve()
    output = (ROOT/args.output).resolve()
    if not source.is_relative_to(ROOT) or not output.is_relative_to(ROOT/'outputs') or output.is_relative_to(source):
        parser.error('Use source within workspace and a new independent directory under outputs')
    print(json.dumps(build(source, output), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
