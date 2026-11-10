"""Read-only inventory; keep reports private because paths can identify local data."""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def inventory(output):
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(ROOT / 'outputs'):
        raise ValueError('Choose a new output directory under outputs/')
    files = []
    for directory, _, names in os.walk(ROOT):
        for name in names:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            try:
                files.append((path, path.stat().st_size))
            except OSError:
                continue
    sizes = defaultdict(int)
    candidates = defaultdict(list)
    protected = {}
    for path, size in files:
        relative = path.relative_to(ROOT).as_posix()
        top = relative.split('/')[0]
        sizes[top] += size
        if top not in {'.venv', '.git'}:
            candidates[size].append(path)
        if top in {'data', 'datasets', 'models', 'adapters', 'evaluations', 'MyAI_Data_Pack_v1'}:
            if '__pycache__' not in path.parts and path.suffix != '.pyc' and '.git' not in path.parts:
                protected[relative] = sha256(path)
    duplicates = []
    for size, paths in candidates.items():
        if not size or len(paths) < 2:
            continue
        groups = defaultdict(list)
        for path in paths:
            groups[sha256(path)].append(path.relative_to(ROOT).as_posix())
        duplicates.extend({'bytes_each': size, 'sha256': digest, 'paths': names}
                          for digest, names in groups.items() if len(names) > 1)
    output.mkdir(parents=True)
    git = lambda *args: subprocess.check_output(['git', *args], cwd=ROOT)
    for name, arguments in {'status.txt': ('status', '--porcelain=v1'),
                            'index_entries.txt': ('ls-files', '--stage'),
                            'staged_stat.txt': ('diff', '--cached', '--stat'),
                            'unstaged_stat.txt': ('diff', '--stat')}.items():
        (output / name).write_bytes(git(*arguments))
    if (ROOT / '.git/index').is_file():
        shutil.copy2(ROOT / '.git/index', output / 'index.backup')
    report = {'bytes': sum(sizes.values()), 'file_count': len(files),
              'top_level_bytes': dict(sorted(sizes.items())),
              'duplicates': duplicates, 'protected_sha256': protected}
    (output / 'inventory.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'bytes': report['bytes'], 'files': len(files), 'duplicate_groups': len(duplicates),
                      'protected_files': len(protected), 'output': str(output)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    inventory(parser.parse_args().output)
