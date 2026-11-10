"""Run offline regression suites and preserve logs, without modifying the catalog.

Pass --legacy-site-packages only to reuse pure-Python packages from an old venv.
The current interpreter's compiled packages take precedence. No package is installed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def protected_hashes():
    files = list((ROOT/'datasets').rglob('*')) + list((ROOT/'data').rglob('*'))
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files) if path.is_file() and '.cache' not in path.parts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='outputs/offline_checks')
    parser.add_argument('--legacy-site-packages')
    parser.add_argument('--include-local-data', action='store_true',
                        help='Also audit/rebuild historical private datasets into a new output; never run by default on a clone')
    args = parser.parse_args()
    output = (ROOT/args.output).resolve()
    protected_roots = [ROOT/name for name in ('data', 'datasets', 'models', 'adapters')]
    if not output.is_relative_to(ROOT) or any(output.is_relative_to(path) for path in protected_roots):
        parser.error('Use a new output folder outside protected inputs, inside the workspace')
    if output.exists() and any(output.iterdir()):
        parser.error('Output already contains files; choose a new output directory')
    output.mkdir(parents=True, exist_ok=True)
    before = protected_hashes()
    (output/'input_hashes.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    commands = [
        ('unit', ['-m', 'unittest', 'discover', '-s', 'tests', '-v']),
        ('preparer', ['-m', 'unittest', 'discover', '-s', 'MyAI_Prepare_Datasets_v2/tests', '-v']),
        ('quality_rules', ['-m', 'unittest', 'discover', '-s', 'MyAI_Quality_Gate_v2_1', '-v']),
        ('pack', ['MyAI_Data_Pack_v1/tools/validate_pack.py']),
        ('db_scratch', ['MyAI_Data_Pack_v1/tools/preflight_db_test.py']),
        ('db_readonly', ['-m', 'scripts.inspect_database', '--output', str(output/'database.json')]),
        ('verify_v2', ['MyAI_Prepare_Datasets_v2/verify_v2.py']),
        ('verify_review', ['MyAI_Prepare_Datasets_v2/verify_v2.py', '--output', 'data/prepared_v2_1_review']),
        ('lengths', ['MyAI_Prepare_Datasets_v2/preflight_train_v2.py', '--output', 'data/prepared_v2_1_review']),
        ('sources', ['MyAI_Search_Data_Preflight_v1/inspect_search_sources.py', '--output', str(output/'search_sources.json')]),
        ('dataset_audit', ['-m', 'scripts.audit_datasets', '--output', str(output/'dataset_audit.json')]),
        ('search_benchmark', ['MyAI_Search_Integration_v2_2/evaluate_search.py', '--output', str(output/'search_benchmark.json')]),
        ('prepare_from_raw', ['MyAI_Prepare_Datasets_v2/prepare_v2.py', '--output', str(output/'prepared_candidate')]),
        ('verify_new_candidate', ['MyAI_Prepare_Datasets_v2/verify_v2.py', '--output', str(output/'prepared_candidate')]),
        ('quality_gate_candidate', ['MyAI_Quality_Gate_v2_1/quality_gate.py', '--input-dir', str(output/'prepared_candidate'), '--output-dir', str(output/'review_candidate')]),
        ('verify_new_review', ['MyAI_Prepare_Datasets_v2/verify_v2.py', '--output', str(output/'review_candidate')]),
        ('audit_new_review', ['-m', 'scripts.audit_datasets', '--input', str(output/'review_candidate'), '--output', str(output/'new_candidate_audit.json')]),
    ]
    if not args.include_local_data:
        commands = [entry for entry in commands if entry[0] in
                    {'unit', 'preparer', 'quality_rules', 'db_scratch', 'search_benchmark'}]
    commands.extend([
        ('regression_42', ['MyAI_Search_Integration_v2_2/evaluate_frozen_holdout.py', '--regression',
                           '--output', str(output/'regression_42.json')]),
        ('frozen_holdout_65', ['MyAI_Search_Integration_v2_2/evaluate_frozen_holdout.py',
                              '--suite', 'evaluations/search_holdout_v24', '--output', str(output/'holdout_65.json')]),
    ])
    results = []
    env = dict(os.environ, PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    for name, command in commands:
        if args.legacy_site_packages:
            bootstrap = ('import sys, runpy\nfrom pathlib import Path\n'
                         + 'sys.path.append(' + repr(str(Path(args.legacy_site_packages).resolve())) + ')\n'
                         + 'args = sys.argv[1:]\n'
                         + "if args[0] == '-m':\n"
                         + '    sys.argv = args[1:]\n'
                         + "    runpy.run_module(args[1], run_name='__main__', alter_sys=True)\n"
                         + 'else:\n    sys.argv = args\n'
                         + '    sys.path.insert(0, str(Path(args[0]).resolve().parent))\n'
                         + "    runpy.run_path(args[0], run_name='__main__')\n")
            command = ['-c', bootstrap] + command
        completed = subprocess.run([sys.executable] + command, cwd=ROOT, env=env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        (output/(name+'.log')).write_text(completed.stdout, encoding='utf-8')
        expected_baseline = False
        if name == 'frozen_holdout_65' and (output/'holdout_65.json').is_file():
            holdout = json.loads((output/'holdout_65.json').read_text(encoding='utf-8'))
            failed_ids = {row['case_id'] for row in holdout.get('cases', []) if not row['passed']}
            expected_baseline = (completed.returncode == 2 and holdout.get('passed') == 63
                                 and holdout.get('total') == 65 and failed_ids == {'H24-063', 'H24-065'})
        results.append({'check': name, 'exit_code': completed.returncode,
                        'expected_baseline_63_of_65': expected_baseline})
        print(name, 'BASELINE_63_65' if expected_baseline else 'PASS' if completed.returncode == 0 else 'FAIL', flush=True)
    after = protected_hashes()
    changes = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    report = {'python': sys.version, 'legacy_site_packages': args.legacy_site_packages,
              'checks': results, 'include_local_data': args.include_local_data, 'protected_input_changes': changes}
    (output/'summary.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return int(bool(changes) or any(row['exit_code'] and not row['expected_baseline_63_of_65'] for row in results))


if __name__ == '__main__':
    raise SystemExit(main())
