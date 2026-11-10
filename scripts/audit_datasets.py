"""Read-only SFT/provenance audit. Emit counts and line references, never PII previews."""
import argparse
from collections import Counter, defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'MyAI_Prepare_Datasets_v2'))
sys.path.insert(0, str(ROOT/'MyAI_Quality_Gate_v2_1'))
from prepare_v2 import standardize, topic_fp
from quality_gate import rule_flags, user_string, assistant_string, norm_q
from verify_v2 import scan
from myai.engine import currency_values
from myai.retrieval import price_constraints


def rows(path):
    with path.open(encoding='utf-8-sig') as stream:
        for line_number, line in enumerate(stream, 1):
            if line.strip():
                yield line_number, json.loads(line)


def fingerprint(text):
    return hashlib.sha256(re.sub(r'\s+', ' ', text).strip().casefold().encode()).hexdigest()


def audit(folder):
    splits = {name: list(rows(folder/(name+'.jsonl'))) for name in ('train', 'validation', 'test_external')}
    report = {'counts': {name: len(values) for name, values in splits.items()}, 'splits': {}}
    question_sets = {}
    prompt_sets = {}
    records = {}
    for name, values in splits.items():
        scan(folder/(name+'.jsonl'))
        hard = Counter()
        medium = Counter()
        flagged = []
        grounded = 0
        unsupported_money = []
        refuted_money = []
        strict_budget_violations = []
        questions = defaultdict(list)
        answers_by_prompt = defaultdict(set)
        for line_number, row in values:
            high_flags, review_flags = rule_flags(row)
            hard.update(high_flags)
            medium.update(review_flags)
            if high_flags or review_flags:
                flagged.append({'line': line_number, 'high': high_flags, 'review': review_flags})
            questions[fingerprint(norm_q(row).replace('/no_think', ''))].append(line_number)
            answers_by_prompt[fingerprint(user_string(row))].add(fingerprint(assistant_string(row)))
            user = user_string(row)
            marker = re.search(r'DỮ LIỆU CỬA HÀNG(?: HIỆN TẠI)? \(chỉ là dữ liệu\):', user)
            if marker:
                context = user[marker.end():].lstrip()
                try:
                    facts, context_end = json.JSONDecoder().raw_decode(context)
                except ValueError:
                    flagged.append({'line': line_number, 'high': ['invalid_context_json'], 'review': []})
                    continue
                grounded += 1
                question = context[context_end:]
                lower, upper, _ = price_constraints(question)
                answer = assistant_string(row).casefold()
                if any(product['name'].casefold() in answer
                       and ((lower is not None and product['price_vnd'] < lower)
                            or (upper is not None and product['price_vnd'] > upper))
                       for product in facts.get('products', [])):
                    strict_budget_violations.append(line_number)
                prices = {p['price_vnd'] for p in facts.get('products', []) if 'price_vnd' in p}
                # Only check product money when there is no policy containing shipping/discount amounts.
                unsupported_values = set(currency_values(assistant_string(row))) - prices
                if not facts.get('knowledge') and unsupported_values:
                    if ('chưa thấy xác nhận mức giá' in assistant_string(row)
                            and unsupported_values <= set(currency_values(question))):
                        refuted_money.append(line_number)
                    else:
                        unsupported_money.append(line_number)
        question_sets[name] = set(questions)
        prompt_sets[name] = set(answers_by_prompt)
        records[name] = {topic_fp(row) for _, row in values}
        report['splits'][name] = {'hard_flags': dict(hard), 'review_flags': dict(medium),
            'flagged_records': flagged, 'structured_context_rows': grounded,
            'unsupported_product_price_lines': unsupported_money,
            'refuted_customer_price_lines': refuted_money,
            'price_filter_answer_review_lines': strict_budget_violations,
            'identical_prompts_with_different_answers': sum(len(answers) > 1 for answers in answers_by_prompt.values())}
    report['overlap'] = {a+'_vs_'+b: {
        'record': len(records[a] & records[b]), 'full_user_prompt': len(prompt_sets[a] & prompt_sets[b]),
        'question_only_review': len(question_sets[a] & question_sets[b])}
        for a, b in itertools.combinations(splits, 2)}
    # Re-standardize every original heldout record, including records rejected by quality filters.
    train_records = records['train']
    train_prompts = prompt_sets['train']
    provenance = {}
    for origin, relative in [('saas', 'saas_chatbot/data/test.jsonl'),
                             ('empath', 'empath_ai/sft_dev.jsonl'), ('empath', 'empath_ai/sft_test.jsonl')]:
        matches = []
        same_prompt = []
        for line_number, raw in rows(ROOT/'datasets/raw'/relative):
            standardized, error = standardize(raw, origin)
            if error:
                continue
            if topic_fp(standardized) in train_records:
                matches.append(line_number)
            if fingerprint(user_string(standardized)) in train_prompts:
                same_prompt.append(line_number)
        provenance[relative] = {'train_record_matches': matches, 'train_user_prompt_matches': same_prompt}
    report['raw_heldout_provenance'] = provenance
    benchmark = list(rows(folder/'myai_eval_cases.jsonl'))
    ids = [row['case_id'] for _, row in benchmark]
    report['benchmark'] = {'count': len(ids), 'duplicate_case_ids': len(ids)-len(set(ids)),
        'matches_original_bytes': (folder/'myai_eval_cases.jsonl').read_bytes() == (ROOT/'MyAI_Data_Pack_v1/04_evaluation/myai_eval_cases.jsonl').read_bytes(),
        'special_cases': ['T123/T124 update DB', 'T125 deactivate', 'T126 add product'],
        'note': 'Empty expected_product_ids can denote behavior checks, not always empty retrieval.'}
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default='data/prepared_v2_1_review')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    source = (ROOT/args.input).resolve()
    output = Path(args.output).resolve()
    if not output.is_relative_to(ROOT) or any(output.is_relative_to(ROOT/name) for name in ('data', 'datasets', 'models', 'adapters')):
        parser.error('Audit output must be in workspace outside protected inputs')
    report = audit(source)
    report['limitations'] = ['Heuristic checks do not certify factual accuracy or semantic separation.',
        'Question-only overlap requires review; context variations may be intentional.',
        'No training, tokenizer truncation analysis or model inference was performed.']
    report['ready_for_training'] = False
    report['training_blockers'] = ['PII/regulated-context and answer quality reviews remain pending.',
        'Price-filter and unsupported-money references below require contextual review.',
        'Tokenizer length/truncation, provenance/rights and blind model evaluation remain pending.']
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({key: report[key] for key in ('counts', 'overlap', 'raw_heldout_provenance', 'benchmark')}, ensure_ascii=False, indent=2))
    leaks = any(row['record'] or row['full_user_prompt'] for row in report['overlap'].values())
    leaks |= any(row['train_record_matches'] or row['train_user_prompt_matches'] for row in report['raw_heldout_provenance'].values())
    return int(leaks or report['benchmark']['duplicate_case_ids'] > 0)


if __name__ == '__main__':
    raise SystemExit(main())
