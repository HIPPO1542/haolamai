"""Download official Qwen3.5 weights and model licensing files (one time)."""
import argparse
import hashlib
import json
from pathlib import Path

MODELS = ('Qwen/Qwen3.5-4B', 'Qwen/Qwen3.5-9B')

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', choices=MODELS, default='Qwen/Qwen3.5-9B')
    p.add_argument('--output', default=None)
    p.add_argument('--revision',default='main',help='Prefer an immutable commit revision for reproducibility')
    p.add_argument('--tokenizer-only',action='store_true',help='Download config/tokenizer only; never claim weights are present')
    args = p.parse_args()
    output = Path(args.output or 'models/' + args.model.split('/')[-1])
    if output.exists() and any(output.iterdir()):raise SystemExit('Output is not empty; choose a new directory, no overwrite')
    from huggingface_hub import HfApi, snapshot_download
    resolved_revision=HfApi().model_info(args.model,revision=args.revision).sha
    if not resolved_revision:raise RuntimeError('Could not resolve immutable upstream revision')
    patterns=['*.json','*.txt','*.model','LICENSE','NOTICE','*.tiktoken','*.jinja']
    if not args.tokenizer_only:patterns.append('*.safetensors')
    snapshot_download(
        repo_id=args.model,
        revision=resolved_revision,local_dir=str(output),allow_patterns=patterns,
    )
    manifest={'model_id':args.model,'requested_revision':args.revision,'resolved_revision':resolved_revision,'tokenizer_only':args.tokenizer_only,
              'config_sha256':hashlib.sha256((output/'config.json').read_bytes()).hexdigest()}
    (output/'myai_download_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Model saved at', output)
    print('Preserve upstream LICENSE/NOTICE if provided by repository.')

if __name__ == '__main__':
    main()
