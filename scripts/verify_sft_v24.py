"""Independently rescan the final candidate and all new oracle-backed records."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from scripts.curate_candidate import question_key
from scripts.dataset_quality_v24 import NearQuestionIndex,estimated_skill
from scripts.grounded_sales_v24 import verify_generated
from scripts.training_data_guard import validate_training_inputs

ROOT=Path(__file__).resolve().parents[1]


def records(path):return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input',default='outputs/v2_4/sft_candidate_final')
    parser.add_argument('--output',required=True);args=parser.parse_args()
    folder=(ROOT/args.input).resolve();output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs/v2_4') or output.exists():parser.error('Use a new v2.4 report path')
    splits={split:records(folder/(split+'.jsonl')) for split in ('train','validation','test_external')}
    validate_training_inputs(folder/'train.jsonl',folder/'validation.jsonl',folder/'test_external.jsonl')
    provenance=records(folder/'provenance.jsonl');assert len(provenance)==len(splits['train'])
    verified=0
    for index,meta in enumerate(provenance):
        assert meta['output_line']==index+1
        if meta['source']=='verified_rule_sales_v24':verify_generated(splits['train'][index],meta);verified+=1
        assert not any(tag in meta['source'] for tag in ('_test','_dev','_validation'))
    heldout=NearQuestionIndex()
    for split in ('test_external','validation'):
        for line,row in enumerate(splits[split],1):heldout.add(row,{'split':split,'line':line})
    matches=[]
    for line,row in enumerate(splits['train'],1):
        match=heldout.match(row)
        if match:matches.append({'train_line':line,'match':match})
    assert not matches
    questions=Counter(question_key(row) for row in splits['train'])
    repeated=[count for count in questions.values() if count>1]
    old=ROOT/'outputs/v2_3/sft_candidate'
    assert (folder/'test_external.jsonl').read_bytes()==(old/'test_external.jsonl').read_bytes()
    assert (folder/'myai_eval_cases.jsonl').read_bytes()==(old/'myai_eval_cases.jsonl').read_bytes()
    report={'counts':{split:len(rows) for split,rows in splits.items()},'generated_oracle_rows_verified':verified,
        'cross_split_near_matches':matches,'test_benchmark_bytes_unchanged':True,
        'within_train_repeated_question_groups':len(repeated),'within_train_max_question_group_rows':max(repeated,default=1),
        'within_train_note':'Some grounded context/counterfactual tasks intentionally reuse question wording inside train only.',
        'source_counts':dict(Counter(meta['source'] for meta in provenance)),
        'classification_scope':'Estimated skills for seed rows; task-specification labels for new synthetic rows',
        'semantic_leakage_certified':False,'ready_for_training':False}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
