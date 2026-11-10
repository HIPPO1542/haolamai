"""Cross-check versioned artifacts and frozen holdout without re-running/tuning it."""
import argparse
import ast
import hashlib
import itertools
import json
from pathlib import Path
import warnings
from scripts.run_offline_checks import protected_hashes
from scripts.curate_candidate import question_key

ROOT=Path(__file__).resolve().parents[1]


def read_json(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def read_jsonl(path):return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs') or output.exists():parser.error('Choose a new report path under outputs')
    base=ROOT/'outputs/v2_3'
    unchanged=protected_hashes()==read_json(base/'original_input_hashes.json')
    assert unchanged,'Original data changed'
    freeze=read_json(ROOT/'evaluations/search_holdout_v23/freeze.json')
    assert all(hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest for relative,digest in freeze['sha256'].items())
    source=ROOT/'outputs/verified_v2_2/review_candidate'
    candidate=base/'sft_candidate'
    assert (candidate/'test_external.jsonl').read_bytes()==(source/'test_external.jsonl').read_bytes()
    sets={split:{question_key(row) for row in read_jsonl(candidate/(split+'.jsonl'))} for split in ('train','validation','test_external')}
    overlaps={a+'_vs_'+b:len(sets[a]&sets[b]) for a,b in itertools.combinations(sets,2)}
    assert not any(overlaps.values())
    search_overlaps={}
    for kind,suffix in [('intent','.jsonl'),('ranking','_queries.jsonl')]:
        groups={split:{row['question_group_sha256'] for row in read_jsonl(base/'search_benchmarks'/kind/(split+suffix))}
                for split in ('train','validation','test')}
        search_overlaps[kind]={a+'_vs_'+b:len(groups[a]&groups[b]) for a,b in itertools.combinations(groups,2)}
        assert not any(search_overlaps[kind].values())
    preflight=read_json(base/'qwen_preflight_verified/report.json')
    assert not preflight['training_started'] and not preflight['paid_resources_used']
    assert not preflight['ready_for_9b_qlora']
    python_files=[]
    with warnings.catch_warnings():
        warnings.simplefilter('error',SyntaxWarning)
        for directory in ('myai','scripts','tests','MyAI_Prepare_Datasets_v2','MyAI_Data_Pack_v1/tools',
                          'MyAI_Quality_Gate_v2_1','MyAI_Search_Data_Preflight_v1','MyAI_Search_Integration_v2_2'):
            for path in (ROOT/directory).rglob('*.py'):
                ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path))
                python_files.append(str(path.relative_to(ROOT)))
    regression=read_json(base/'full_regression/summary.json')
    assert all(check['exit_code']==0 for check in regression['checks'])
    report={'protected_inputs_unchanged':unchanged,'frozen_algorithm_unchanged':True,'sft_question_overlap':overlaps,
        'search_question_overlap':search_overlaps,'python_source_files_parsed':len(python_files),
        'regression_checks_passed':len(regression['checks']),
        'new_holdout':{key:value for key,value in read_json(base/'heldout_results.json').items() if key!='cases'},
        'qwen_ready':False,'old_venv_still_exists':(ROOT/'.venv/pyvenv.cfg').is_file()}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
