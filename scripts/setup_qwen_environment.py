"""Provision a fresh ABI-consistent ML venv; never train or reuse old binaries.

Run on Windows/Linux with network access or an ABI-matched offline wheelhouse.
Creating a venv is not evidence that Qwen imports work: the report separates them.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--base-python',default=sys.executable)
    parser.add_argument('--environment',default='.venv')
    parser.add_argument('--report-dir',required=True)
    parser.add_argument('--wheelhouse')
    parser.add_argument('--cuda-index',default='https://download.pytorch.org/whl/cu132')
    parser.add_argument('--install',action='store_true',help='Install free software dependencies only, never model/training')
    args=parser.parse_args()
    target=(ROOT/args.environment).resolve();report_dir=(ROOT/args.report_dir).resolve()
    if target.parent!=ROOT or not (target.name=='.venv' or target.name.startswith('.venv-')) or target.exists():
        parser.error('Choose a new .venv-* directory directly inside the workspace')
    if not report_dir.is_relative_to(ROOT/'outputs') or report_dir.exists():
        parser.error('Choose a new report directory under outputs')
    base=subprocess.run([args.base_python,'-c','import sys,json,struct; print(json.dumps(dict(version=list(sys.version_info[:3]),bits=struct.calcsize("P")*8,executable=sys.executable)))'],
                        capture_output=True,text=True,encoding='utf-8')
    if base.returncode:raise RuntimeError('Base interpreter cannot run: '+base.stderr)
    base_info=json.loads(base.stdout)
    if base_info['bits']!=64 or base_info['version'][:2] not in ([3,11],[3,12]):
        raise ValueError('Use accessible x64 Python 3.11 or 3.12 with matching wheels')
    report_dir.mkdir(parents=True)
    subprocess.run([args.base_python,'-m','venv',str(target)],check=True)
    python=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    install_results=[]
    network=None
    if args.install:
        if not args.wheelhouse:
            try:
                with urllib.request.urlopen(args.cuda_index+'/torch/',timeout=10) as response:
                    network={'status':'PASS','http_status':response.status}
            except Exception as error:
                network={'status':'BLOCKED','error':type(error).__name__+': '+str(error)}
        common=['--disable-pip-version-check','--retries','0','--timeout','10']
        offline=['--no-index','--find-links',str(Path(args.wheelhouse).resolve())] if args.wheelhouse else []
        plans=[['torch','torchvision']+(offline or ['--index-url',args.cuda_index]),
               ['-r',str(ROOT/'requirements.txt')]+offline]
        for index,arguments in enumerate(plans):
            completed=subprocess.run([str(python),'-m','pip','install']+common+arguments,cwd=ROOT,
                                      capture_output=True,text=True,encoding='utf-8',errors='replace')
            (report_dir/f'install_{index}.log').write_text(completed.stdout+completed.stderr,encoding='utf-8')
            install_results.append({'step':index,'exit_code':completed.returncode})
            if completed.returncode:break
    diagnostics=report_dir/'imports.json'
    checked=subprocess.run([str(python),'-m','scripts.diagnose_environment','--output',str(diagnostics)],cwd=ROOT,
                           capture_output=True,text=True,encoding='utf-8',errors='replace')
    (report_dir/'imports.log').write_text(checked.stdout+checked.stderr,encoding='utf-8')
    dependency_check=subprocess.run([str(python),'-m','pip','check'],capture_output=True,text=True,encoding='utf-8')
    (report_dir/'pip_check.log').write_text(dependency_check.stdout+dependency_check.stderr,encoding='utf-8')
    report={'base':base_info,'python':str(python),'created_clean_venv':True,'system_site_packages':False,
            'old_environment_modified':False,'copied_old_binary_packages':False,'installation':install_results,
            'full_import_exit_code':checked.returncode,'pip_check_exit_code':dependency_check.returncode,
            'network_probe':network,
            'ready_for_qwen_imports':checked.returncode==0,'training_started':False}
    (report_dir/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if checked.returncode==0 and dependency_check.returncode==0 else 2


if __name__=='__main__':raise SystemExit(main())
