"""Snapshot source and protected inputs without changing prior outputs or data."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
SOURCE_DIRS=('myai','scripts','windows','tests','docs','MyAI_Search_Integration_v2_2')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs():
    result={}
    for folder in ('data','datasets','models','adapters','outputs'):
        for path in (ROOT/folder).rglob('*'):
            if not path.is_file() or '.cache' in path.parts or '__pycache__' in path.parts:
                continue
            if path.is_relative_to(ROOT/'outputs/v2_4'):
                continue
            result[str(path.relative_to(ROOT))]=sha(path)
    for folder in ('.venv','.venv-backend-v23'):
        for name in ('pyvenv.cfg','Scripts/python.exe'):
            path=ROOT/folder/name
            if path.is_file():result[str(path.relative_to(ROOT))]=sha(path)
    for path in (ROOT/'evaluations').rglob('*'):
        if path.is_file() and not any(path.is_relative_to(ROOT/'evaluations'/folder)
                                     for folder in ('search_holdout_v24','sales_grounding_v24')):
            result[str(path.relative_to(ROOT))]=sha(path)
    return result


def sources():
    paths=[path for folder in SOURCE_DIRS for path in (ROOT/folder).rglob('*')
           if path.is_file() and path.suffix in ('.py','.ps1','.md','.json') and '__pycache__' not in path.parts]
    paths += [path for path in ROOT.iterdir() if path.is_file() and path.suffix in ('.md','.txt')]
    return {str(path.relative_to(ROOT)):sha(path) for path in paths}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['capture','verify'])
    parser.add_argument('--output',required=True);args=parser.parse_args()
    output=(ROOT/args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs/v2_4') or output.exists():parser.error('Use a new directory under outputs/v2_4')
    output.mkdir(parents=True)
    if args.mode=='capture':
        report={'protected':inputs(),'source':sources()}
        for relative in report['source']:
            target=output/'source_backup'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/relative,target)
    else:
        original=json.loads((ROOT/'outputs/v2_4/baseline/report.json').read_text(encoding='utf-8'))
        current=inputs();code=sources()
        changes=[name for name in original['protected'].keys()|current.keys() if original['protected'].get(name)!=current.get(name)]
        report={'protected_changes':sorted(changes),'source_added':sorted(code.keys()-original['source'].keys()),
                'source_changed':sorted(name for name in code.keys()&original['source'].keys() if code[name]!=original['source'][name])}
        if changes:raise RuntimeError('Protected input changes detected; inspect before continuing')
    (output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Snapshot',args.mode,'complete')


if __name__=='__main__':main()
