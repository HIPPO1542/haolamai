"""Isolated import diagnostics; metadata presence alone never counts as import PASS."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBES = {
    'fastapi': 'import fastapi,uvicorn,pydantic',
    'torch': 'import torch; print(torch.__version__); print("CUDA",torch.cuda.is_available())',
    'torchvision': 'import torchvision; print(torchvision.__version__)',
    'transformers': 'from transformers import AutoTokenizer,Qwen3_5ForCausalLM,BitsAndBytesConfig',
    'datasets': 'from datasets import load_dataset,Dataset',
    'peft': 'from peft import LoraConfig,PeftModel,prepare_model_for_kbit_training',
    'trl': 'from trl import SFTConfig,SFTTrainer',
    'accelerate': 'import accelerate',
    'bitsandbytes': 'import bitsandbytes',
    'huggingface_hub': 'from huggingface_hub import snapshot_download',
    'safetensors': 'from safetensors.torch import save_file,load_file',
    'tokenizers': 'import tokenizers',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--legacy-site-packages')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if not output.is_relative_to(ROOT/'outputs') or output.exists():
        parser.error('Use a new report path inside workspace')
    prefix = ''
    if args.legacy_site_packages:
        prefix = 'import sys; sys.path.append('+repr(str(Path(args.legacy_site_packages).resolve()))+'); '
    probes = {}
    for name, code in PROBES.items():
        try:
            process = subprocess.run([args.python, '-c', prefix+code], cwd=ROOT,
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45)
            probes[name] = {'status': 'PASS' if process.returncode == 0 else 'BLOCKED',
                'exit_code': process.returncode, 'stdout': process.stdout, 'stderr': process.stderr}
        except (OSError, subprocess.TimeoutExpired) as error:
            probes[name] = {'status': 'BLOCKED', 'error': str(error)}
        print(name, probes[name]['status'], flush=True)
    report = {'python': args.python, 'legacy_path_for_diagnosis_only': args.legacy_site_packages,
              'probes': probes, 'full_qwen_imports_pass': all(probe['status']=='PASS' for probe in probes.values())}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['full_qwen_imports_pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
