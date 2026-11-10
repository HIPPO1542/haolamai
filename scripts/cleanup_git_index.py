"""Plan/apply narrowly scoped untracking. Never delete working-tree files or stage code."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ('datasets/raw/', 'outputs/', 'data/prepared', 'data/search_data_preflight/',
            'MyAI_Data_Pack_v1/03_sft_addon/')
EXACT = {'datasets/raw/wands', 'requirements-app.txt', 'requirements-train.txt',
         'MyAI_Data_Pack_v1/01_database/MyAI_DanhMuc_va_ChinhSach.xlsx'}


def index_entries():
    entries = subprocess.check_output(['git', 'ls-files', '--stage', '-z'], cwd=ROOT).decode('utf-8')
    return dict(entry.split('\t', 1)[::-1] for entry in entries.split('\0') if entry)


def excluded(path):
    return path in EXACT or path.startswith(PREFIXES)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, help='New JSON plan, or existing plan with --apply')
    parser.add_argument('--apply', action='store_true', help='Untrack only reviewed plan entries; keep all local data')
    args = parser.parse_args()
    plan_path = Path(args.plan).resolve()
    if not plan_path.is_relative_to(ROOT / 'outputs'):
        parser.error('Keep the private plan under outputs/')
    current = index_entries()
    if not args.apply:
        if plan_path.exists():
            parser.error('Plan already exists')
        plan = {path: entry for path, entry in current.items() if excluded(path)}
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f'PLAN: {len(plan)} entries; no index/files changed')
        return
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if not plan or any(not excluded(path) for path in plan):
        parser.error('Plan contains an unapproved path or is empty')
    if any(current.get(path) != entry for path, entry in plan.items()):
        parser.error('Index changed since plan; review and create a new plan')
    backup = plan_path.with_suffix('.index.backup')
    if backup.exists():
        parser.error('Backup already exists; inspect previous attempt before retrying')
    shutil.copy2(ROOT / '.git/index', backup)
    # The exact modes/OIDs were checked above. -f is needed for the newly staged
    # WANDS gitlink; --cached ALWAYS keeps working-tree files, including nested .git.
    subprocess.run(['git', 'rm', '--cached', '-f', '--', *plan], cwd=ROOT, check=True)
    after = index_entries()
    expected = {path: entry for path, entry in current.items() if path not in plan}
    if after != expected:
        raise RuntimeError('Unexpected index change; inspect backup. No automatic reset attempted.')
    print(f'Untracked {len(plan)} entries; all working-tree files preserved')


if __name__ == '__main__':
    main()
