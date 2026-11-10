"""Recover a separate backend environment from verified pure-Python distributions.

Never rewrites the old venv. Compiled Python 3.11 packages are never copied into
Python 3.12. The new environment inherits the working base runtime explicitly.
This repairs backend/offline tools only, not the unavailable CUDA/Qwen stack.
"""
import argparse
import base64
import csv
import hashlib
import importlib.metadata as metadata
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def make_wheel(distribution, destination):
    info = Path(distribution._path)
    site = info.parent
    wheel_metadata = (info/'WHEEL').read_text(encoding='utf-8')
    if 'Root-Is-Purelib: true' not in wheel_metadata or 'Tag: py3-none-any' not in wheel_metadata:
        raise ValueError('Cannot reuse a compiled/platform-specific distribution: '+info.name)
    name = distribution.metadata['Name'].replace('-', '_')
    filename = destination/f'{name}-{distribution.version}-py3-none-any.whl'
    with zipfile.ZipFile(filename, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, digest, _ in csv.reader(io.StringIO(distribution.read_text('RECORD'))):
            parts = Path(relative).parts
            if '..' in parts or '__pycache__' in parts or relative.endswith('.pyc'):
                continue
            path = site/relative
            if not path.resolve().is_relative_to(site.resolve()):
                raise ValueError('Distribution file escapes source site-packages')
            if not path.is_file():
                raise ValueError('Installed distribution has a missing file: '+relative)
            content = path.read_bytes()
            if digest:
                algorithm, expected = digest.split('=', 1)
                actual = base64.urlsafe_b64encode(hashlib.new(algorithm, content).digest()).decode().rstrip('=')
                if actual != expected:
                    raise ValueError('Installed distribution hash mismatch: '+relative)
            archive.writestr(relative, content)
    return filename


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', default='.venv/Lib/site-packages')
    parser.add_argument('--output', default='.venv-backend-v23')
    parser.add_argument('--report-dir', required=True)
    args = parser.parse_args()
    source = (ROOT/args.source).resolve()
    target = (ROOT/args.output).resolve()
    report_dir = (ROOT/args.report_dir).resolve()
    if target.parent != ROOT or not target.name.startswith('.venv-') or target.exists():
        parser.error('Choose a new environment directory inside the workspace')
    if not report_dir.is_relative_to(ROOT/'outputs') or report_dir.exists():
        parser.error('Choose a new report directory in the workspace')
    report_dir.mkdir(parents=True)
    wheelhouse = report_dir/'wheelhouse'
    wheelhouse.mkdir()
    old = {canonicalize_name(dist.metadata['Name']): dist for dist in metadata.distributions(path=[str(source)])}
    current = {canonicalize_name(dist.metadata['Name']): dist for dist in metadata.distributions()}
    pending = [Requirement(name) for name in ('fastapi', 'uvicorn', 'httpx')]
    selected = {}
    while pending:
        requirement = pending.pop()
        if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
            continue
        name = canonicalize_name(requirement.name)
        available = selected.get(name) or current.get(name)
        if available and available.version in requirement.specifier:
            continue
        distribution = old.get(name)
        if distribution is None or distribution.version not in requirement.specifier:
            raise ValueError('No compatible local distribution for '+str(requirement))
        make_wheel(distribution, wheelhouse)
        selected[name] = distribution
        pending.extend(Requirement(value) for value in distribution.requires or [])
    subprocess.run([sys.executable, '-m', 'venv', '--system-site-packages', str(target)], check=True)
    python = target/'Scripts/python.exe'
    command = [str(python), '-m', 'pip', 'install', '--no-index', '--no-deps']
    command += [str(path) for path in sorted(wheelhouse.glob('*.whl'))]
    installed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
    (report_dir/'install.log').write_text(installed.stdout+installed.stderr, encoding='utf-8')
    if installed.returncode:
        raise RuntimeError('Offline installation failed; inspect install.log. Old venv unchanged.')
    checked = subprocess.run([str(python), '-m', 'pip', 'check'], capture_output=True, text=True, encoding='utf-8')
    (report_dir/'pip_check.log').write_text(checked.stdout+checked.stderr, encoding='utf-8')
    report = {'backend_python': str(python), 'base_python': sys.executable,
        'inherits_base_site_packages': True, 'copied_pure_distributions': {name: dist.version for name, dist in selected.items()},
        'old_environment_modified': False, 'qwen_environment_repaired': False,
        'pip_check_exit_code': checked.returncode}
    (report_dir/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    return checked.returncode


if __name__ == '__main__':
    raise SystemExit(main())
