"""Final evidence checks, including the owner's explicit removal of all venvs."""
import argparse
import ast
import hashlib
import itertools
import json
from pathlib import Path
import warnings
from packaging.requirements import Requirement
from scripts.audit_workspace import inputs,sources

ROOT=Path(__file__).resolve().parents[1]


def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def jsonl(path):return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs/v2_4') or output.exists():parser.error('Use a new v2.4 report path')
    baseline=load(ROOT/'outputs/v2_4/baseline/report.json');current=inputs()
    differences=[name for name in baseline['protected'].keys()|current.keys() if baseline['protected'].get(name)!=current.get(name)]
    allowed_prefixes=('.venv/','.venv-backend-v23/')
    authorized=[name for name in differences if name.replace('\\','/').startswith(allowed_prefixes) and name not in current]
    unexpected=sorted(set(differences)-set(authorized));assert not unexpected,unexpected
    cleanup=load(ROOT/'outputs/v2_4/environment/user_requested_cleanup.json')
    assert {row['Name'] for row in cleanup}=={'.venv','.venv-backend-v23','.venv-qwen-v24'}
    assert all(not row['Exists'] and not (ROOT/row['Name']).exists() for row in cleanup)
    suite=ROOT/'evaluations/search_holdout_v24';freeze=load(suite/'freeze.json')
    assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in freeze['sha256'].items())
    candidate=ROOT/'outputs/v2_4/sft_candidate_final';seed=ROOT/'outputs/v2_3/sft_candidate'
    assert (candidate/'test_external.jsonl').read_bytes()==(seed/'test_external.jsonl').read_bytes()
    assert (candidate/'myai_eval_cases.jsonl').read_bytes()==(seed/'myai_eval_cases.jsonl').read_bytes()
    source=ROOT/'outputs/v2_4/search_benchmarks_verified'
    overlaps={}
    for kind,suffix in [('intent','.jsonl'),('ranking','_queries.jsonl')]:
        groups={split:{row['question_group_sha256'] for row in jsonl(source/kind/(split+suffix))} for split in ('train','validation','test')}
        overlaps[kind]={a+'_vs_'+b:len(groups[a]&groups[b]) for a,b in itertools.combinations(groups,2)}
        assert not any(overlaps[kind].values())
    clean_pairs={}
    for split in ('train','validation','test'):
        for row in jsonl(source/'ranking'/(split+'_judgments.jsonl')):
            pair=(row['query_id'],row['product_id']);assert pair not in clean_pairs;clean_pairs[pair]=row['label']
    conflicts={(row['query_id'],row['product_id']) for row in jsonl(source/'ranking/conflicts.jsonl')}
    assert not conflicts&clean_pairs.keys()
    dependencies=[]
    for line in (ROOT/'requirements.txt').read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#') or line.startswith('--'):continue
        dependencies.append(str(Requirement(line)))
    parsed=[]
    with warnings.catch_warnings():
        warnings.simplefilter('error',SyntaxWarning)
        for folder in ('myai','scripts','tests','MyAI_Prepare_Datasets_v2','MyAI_Data_Pack_v1/tools',
                       'MyAI_Quality_Gate_v2_1','MyAI_Search_Data_Preflight_v1','MyAI_Search_Integration_v2_2'):
            for path in (ROOT/folder).rglob('*.py'):
                ast.parse(path.read_text(encoding='utf-8-sig'),filename=str(path));parsed.append(str(path.relative_to(ROOT)))
    code=sources();holdout=load(ROOT/'outputs/v2_4/holdout_v24.json')
    preflight=load(ROOT/'outputs/v2_4/preflight_after_cleanup/report.json')
    assert not preflight['training_started'] and not preflight['paid_resources_used'] and not preflight['ready_for_training']
    train_text=(candidate/'train.jsonl').read_text(encoding='utf-8')
    catalog=load(suite/'catalog.json')
    names_in_train=[row['name'] for row in catalog if row['name'] in train_text]
    supplemental=ROOT/'evaluations/sales_grounding_v24'
    supplement_manifest=load(supplemental/'manifest.json')
    assert hashlib.sha256((supplemental/'cases.jsonl').read_bytes()).hexdigest()==supplement_manifest['sha256']
    assert not supplement_manifest['real_qwen_inference_executed'] and supplement_manifest['not_for_training']
    report={'unexpected_protected_changes':unexpected,'authorized_old_venv_manifest_removals':authorized,
        'all_three_venvs_deleted':True,'data_datasets_previous_outputs_unchanged':True,
        'holdout_algorithm_unchanged_after_freeze':True,'holdout_result':{'passed':holdout['passed'],'total':holdout['total']},
        'new_holdout_names_found_in_final_sft':names_in_train,'test_benchmark_bytes_unchanged':True,
        'search_split_overlap':overlaps,'wands_clean_unique_pairs':len(clean_pairs),'conflict_pairs_excluded':len(conflicts),
        'requirements_parsed':dependencies,'dependency_installation_verified':False,
        'supplemental_grounding_eval':supplement_manifest,
        'python_files_parsed':len(parsed),'source_added':sorted(code.keys()-baseline['source'].keys()),
        'source_modified':sorted(name for name in code.keys()&baseline['source'].keys() if code[name]!=baseline['source'][name]),
        'ready_for_training':False,'current_ml_api_tests_require_user_install':True}
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:value for key,value in report.items() if key not in ('requirements_parsed','source_added','source_modified')},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
