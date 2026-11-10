"""Rebalance a new candidate with provenance, reversible quarantine and verified rules."""
import argparse
from collections import Counter,defaultdict
import hashlib
import itertools
import json
from pathlib import Path

from scripts.audit_datasets import rows,standardize,topic_fp
from scripts.curate_candidate import question_key,source_hash,write_rows,CONTEXT
from scripts.dataset_quality_v24 import SKILLS,estimated_skill,extra_risks,answer_template,NearQuestionIndex
from scripts.grounded_sales_v24 import generate,verify_generated
from scripts.training_data_guard import validate_training_inputs
from MyAI_Quality_Gate_v2_1.quality_gate import user_string
from MyAI_Prepare_Datasets_v2.prepare_v2 import SYSTEM as PREPARED_SYSTEM
from MyAI_Prepare_Datasets_v2.synthetic_cases import generate_grounded_examples

ROOT=Path(__file__).resolve().parents[1]
CAPS={'product_lookup':1600,'advice_comparison_multiturn':800,'policy':600,
      'customer_support':600,'missing_scope_safety':400}


def raw_provenance():
    mapping=defaultdict(set)
    paths=[('saas','saas_train','datasets/raw/saas_chatbot/data/train.jsonl'),
           ('empath','empath_train','datasets/raw/empath_ai/sft_train.jsonl'),
           ('addon','addon_train','MyAI_Data_Pack_v1/03_sft_addon/myai_sft_addon_train.jsonl'),
           ('saas','saas_test','datasets/raw/saas_chatbot/data/test.jsonl'),
           ('empath','empath_dev','datasets/raw/empath_ai/sft_dev.jsonl'),
           ('empath','empath_test','datasets/raw/empath_ai/sft_test.jsonl'),
           ('addon','addon_validation','MyAI_Data_Pack_v1/03_sft_addon/myai_sft_addon_validation.jsonl')]
    for origin,label,relative in paths:
        for _,raw in rows(ROOT/relative):
            record,error=standardize(raw,origin)
            if not error:mapping[topic_fp(record)].add(label)
    for record in generate_grounded_examples(seed=42,n=1500,system=PREPARED_SYSTEM):
        mapping[topic_fp(record)].add('synthetic_v2')
    return mapping


def source_for(row,mapping):
    matched=mapping.get(topic_fp(row))
    if matched:return '+'.join(sorted(matched)),'normalized_raw_record_match'
    if 'SYV2-' in user_string(row):return 'synthetic_v2','explicit_generated_id_marker'
    return 'unresolved_seed_source','unresolved'


def build(source,output,groups=72):
    if output.exists():raise ValueError('Output exists; choose a new directory')
    original={split:list(rows(source/(split+'.jsonl'))) for split in ('train','validation','test_external')}
    input_hashes={name:source_hash(source/name) for name in ('train.jsonl','validation.jsonl','test_external.jsonl','myai_eval_cases.jsonl')}
    mapping=raw_provenance();before_skills=Counter(estimated_skill(row) for _,row in original['train'])
    before_sources=Counter(source_for(row,mapping)[0] for _,row in original['train'])
    output.mkdir(parents=True)
    heldout=NearQuestionIndex();reserved=set()
    for line,row in original['test_external']:
        heldout.add(row,{'split':'test_external','line':line});reserved.add(question_key(row))
    quarantine=[];validation=[];provenance=[]
    for line,row in original['validation']:
        risks=extra_risks(row);near=heldout.match(row)
        if question_key(row) in reserved:risks.append('exact_heldout_question')
        if near:risks.append('near_heldout_question')
        if risks:quarantine.append({'source':'v23_validation','line':line,'reasons':sorted(set(risks)),'near_match':near})
        else:validation.append(row)
    for line,row in enumerate(validation,1):
        heldout.add(row,{'split':'validation','line':line});reserved.add(question_key(row))
    pool=defaultdict(list)
    for line,row in original['train']:
        risks=extra_risks(row);near=heldout.match(row)
        if question_key(row) in reserved:risks.append('exact_heldout_question')
        if near:risks.append('near_heldout_question')
        source_name,method=source_for(row,mapping)
        skill=estimated_skill(row)
        if risks:quarantine.append({'source':'v23_train','line':line,'reasons':sorted(set(risks)),'near_match':near})
        else:pool[skill].append((row,{'source':source_name,'source_method':method,'source_line':line,
                                   'skill':skill,'skill_method':'estimated_rule_classifier'}))
    # Add only examples for which an explicit catalog/task oracle has passed.
    generated_count=0
    for row,meta in generate(groups):
        verify_generated(row,meta);generated_count+=1
        near=heldout.match(row)
        if question_key(row) in reserved or near:
            quarantine.append({'source':meta['source'],'example_id':meta['example_id'],
                               'reasons':['generated_question_reserved_for_heldout'],'near_match':near});continue
        pool[meta['skill']].append((row,dict(meta,source_method='generated_and_oracle_verified',skill_method='verified_task_specification')))
    train=[];counts=Counter();templates=Counter()
    for skill in SKILLS:
        # New audited DB scenarios get priority; seed selection is deterministic.
        ordered=sorted(pool[skill],key=lambda pair:(pair[1]['source']!='verified_rule_sales_v24',
                        hashlib.sha256(json.dumps(pair[0],sort_keys=True,ensure_ascii=False).encode()).hexdigest()))
        for row,meta in ordered:
            reasons=[]
            template=(meta['source'],answer_template(row))
            if skill=='customer_support' and templates[template]>=6:reasons.append('repeated_support_answer_template_cap')
            if counts[skill]>=CAPS[skill]:reasons.append('skill_balance_cap')
            if reasons:
                quarantine.append({'source':meta['source'],'line':meta.get('source_line'),
                    'example_id':meta.get('example_id'),'reasons':reasons});continue
            templates[template]+=1;counts[skill]+=1;train.append(row)
            provenance.append(dict(meta,output_split='train',output_line=len(train),record_sha256=topic_fp(row)))
    for split,records in [('train',train),('validation',validation)]:write_rows(output/(split+'.jsonl'),records)
    (output/'test_external.jsonl').write_bytes((source/'test_external.jsonl').read_bytes())
    (output/'myai_eval_cases.jsonl').write_bytes((source/'myai_eval_cases.jsonl').read_bytes())
    write_rows(output/'provenance.jsonl',provenance);write_rows(output/'quarantine_references.jsonl',quarantine)
    validate_training_inputs(output/'train.jsonl',output/'validation.jsonl',output/'test_external.jsonl')
    sets={split:{question_key(row) for row in records} for split,records in [('train',train),('validation',validation),('test_external',[row for _,row in original['test_external']])]}
    overlap={a+'_vs_'+b:len(sets[a]&sets[b]) for a,b in itertools.combinations(sets,2)}
    assert not any(overlap.values())
    assert input_hashes=={name:source_hash(source/name) for name in input_hashes}
    after_sources=Counter(meta['source'] for meta in provenance)
    after_methods=Counter(meta['skill_method'] for meta in provenance)
    assert not any('test' in meta['source'] or 'validation' in meta['source'] or 'dev' in meta['source'] for meta in provenance)
    evaluation_distribution={}
    for split,records in [('validation',validation),('test_external',[row for _,row in original['test_external']])]:
        evaluation_distribution[split]={'skill_estimates':dict(Counter(estimated_skill(row) for row in records)),
            'sources':dict(Counter(source_for(row,mapping)[0] for row in records))}
    report={'original_counts':{split:len(records) for split,records in original.items()},
        'candidate_counts':{'train':len(train),'validation':len(validation),'test_external':len(original['test_external'])},
        'independent_benchmark':len(list(rows(source/'myai_eval_cases.jsonl'))),'input_sha256':input_hashes,
        'original_train_skill_estimates':dict(before_skills),'original_train_sources':dict(before_sources),
        'train_skill_distribution':{skill:{'rows':counts[skill],'fraction':round(counts[skill]/len(train),5)} for skill in SKILLS},
        'skill_classification_methods':dict(after_methods),'source_distribution':dict(after_sources),
        'evaluation_distributions':evaluation_distribution,
        'generated_rows_oracle_verified':generated_count,'generated_rows_kept':after_sources['verified_rule_sales_v24'],
        'quarantine_rows':len(quarantine),'quarantine_reasons':dict(Counter(reason for row in quarantine for reason in row['reasons'])),
        'question_group_overlap':overlap,'near_duplicate_method':{'unit':'current customer question','min_words':8,
           'similarity':'word trigram Jaccard >=0.82 with identical numeric token sets','semantic_certification':False},
        'training_skill_caps':CAPS,'test_copied_byte_for_byte':source_hash(output/'test_external.jsonl')==input_hashes['test_external.jsonl'],
        'ready_for_training':False,'limitations':['Existing-row skills are heuristic estimates, not manually verified proportions.',
           'New synthetic skills/gold are determined by task specification; template diversity remains limited.',
           'Near-duplicate checks detect lexical similarity, not all paraphrases or semantic leakage.',
           'Rights, full factual/privacy review, real tokenizer/loss-mask and Qwen checks remain required.']}
    (output/'audit_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',default='outputs/v2_3/sft_candidate')
    parser.add_argument('--output',required=True);parser.add_argument('--groups',type=int,default=72);args=parser.parse_args()
    output=(ROOT/args.output).resolve();source=(ROOT/args.input).resolve()
    if not source.is_relative_to(ROOT) or not output.is_relative_to(ROOT/'outputs/v2_4') or output.is_relative_to(source):parser.error('Use separate workspace inputs and a new v2.4 output')
    if not 1<=args.groups<=100:parser.error('Synthetic groups must be between 1 and 100')
    print(json.dumps(build(source,output,args.groups),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
