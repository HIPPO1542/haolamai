"""Read-only Qwen readiness checks; no optimizer, paid service or weight download."""
import argparse
import ast
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import statistics
import sys

from scripts.training_data_guard import validate_training_inputs

ROOT = Path(__file__).resolve().parents[1]
LIBRARIES = ['torch', 'transformers', 'datasets', 'peft', 'trl', 'accelerate',
             'bitsandbytes', 'huggingface_hub', 'safetensors', 'tokenizers']


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def run_preflight(model, train, validation, output, max_length=1024):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT/'outputs') or output.exists():
        raise ValueError('Preflight requires a new directory under outputs')
    output.mkdir(parents=True)
    report = {'training_started': False, 'paid_resources_used': False, 'checks': {}, 'ready_for_9b_qlora': False}
    checks = report['checks']
    try:
        validate_training_inputs(train, validation)
        checks['data_format_and_split'] = {'status': 'PASS', 'train_rows': len(read_rows(train)),
                                         'validation_rows': len(read_rows(validation))}
    except (OSError, ValueError) as error:
        checks['data_format_and_split'] = {'status': 'BLOCKED', 'error': str(error)}
    imported = {}
    for name in LIBRARIES:
        try:
            imported[name] = importlib.import_module(name)
            checks['import_'+name] = {'status': 'PASS', 'version': importlib.metadata.version(name)}
        except Exception as error:
            checks['import_'+name] = {'status': 'BLOCKED', 'error': type(error).__name__+': '+str(error)}
    # Exercise atomic checkpoint file I/O without changing models/adapters.
    temporary = output/'checkpoint-write.tmp'
    final = output/'checkpoint-write.json'
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump({'preflight_only': True}, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, final)
    checks['checkpoint_filesystem'] = {'status': 'PASS', 'roundtrip': json.loads(final.read_text()) == {'preflight_only': True}}
    checks['torch_safetensors_checkpoint'] = {'status': 'BLOCKED', 'reason': 'Requires importable torch and safetensors'}
    if 'torch' in imported and 'safetensors' in imported:
        try:
            torch = imported['torch']
            from safetensors.torch import save_file, load_file
            tensor = torch.arange(4)
            torch.save({'probe': tensor}, output/'probe.pt')
            restored = torch.load(output/'probe.pt', weights_only=True, map_location='cpu')
            save_file({'probe': tensor}, str(output/'probe.safetensors'))
            assert torch.equal(restored['probe'], load_file(str(output/'probe.safetensors'))['probe'])
            checks['torch_safetensors_checkpoint'] = {'status': 'PASS', 'scope': 'Small CPU tensors; no model or optimizer'}
        except Exception as error:
            checks['torch_safetensors_checkpoint'] = {'status': 'BLOCKED', 'error': str(error)}
    checks['qlora_api'] = {'status': 'BLOCKED', 'reason': 'Requires importable transformers, peft, trl'}
    if all(name in imported for name in ('transformers', 'peft', 'trl')):
        try:
            from transformers import BitsAndBytesConfig, Qwen3_5ForCausalLM
            from peft import LoraConfig
            from trl import SFTConfig, SFTTrainer
            BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True)
            lora = LoraConfig(r=16, lora_alpha=32, target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'], task_type='CAUSAL_LM')
            lora.save_pretrained(output/'lora_config')
            SFTConfig(output_dir=str(output/'not_a_training_run'), max_length=max_length,
                      completion_only_loss=True, report_to='none', use_cpu=True, bf16=False)
            checks['qlora_api'] = {'status': 'PASS', 'scope': 'Constructed configs only; model not loaded and trainer not run'}
        except Exception as error:
            checks['qlora_api'] = {'status': 'BLOCKED', 'error': str(error)}
    checks['tokenizer'] = {'status': 'BLOCKED', 'reason': 'Local tokenizer files or compatible transformers unavailable'}
    model = Path(model)
    shards = list(model.glob('*.safetensors'))
    checks['model_weights'] = {'status':'PASS' if (model/'config.json').is_file() and shards else 'BLOCKED',
        'local_safetensors_files': len(shards), 'reason':'Presence only; model loading and architecture compatibility still unverified'}
    if 'transformers' in imported and (model/'tokenizer_config.json').is_file() and (model/'tokenizer.json').is_file():
        try:
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(str(model), local_files_only=True)
            statistics_by_split = {}
            for split, path in [('train',train),('validation',validation)]:
                lengths = []
                no_completion = 0
                truncated = 0
                for row in read_rows(path):
                    prompt = tokenizer.apply_chat_template(row['prompt'], tokenize=True, return_dict=False,
                        add_generation_prompt=True, enable_thinking=False)
                    full = tokenizer.apply_chat_template(row['prompt']+row['completion'], tokenize=True,
                        return_dict=False, enable_thinking=False)
                    lengths.append(len(full))
                    truncated += len(full) > max_length
                    no_completion += len(prompt) >= min(len(full), max_length)
                statistics_by_split[split] = {'rows':len(lengths), 'mean_tokens':statistics.mean(lengths),
                    'p95_tokens':sorted(lengths)[int(len(lengths)*.95)], 'truncated_rows':truncated,
                    'rows_without_completion_at_requested_max_length':no_completion}
            checks['tokenizer'] = {'status':'PASS' if all(not values['rows_without_completion_at_requested_max_length'] for values in statistics_by_split.values()) else 'BLOCKED',
                'max_length': max_length, 'splits': statistics_by_split}
        except Exception as error:
            checks['tokenizer'] = {'status': 'BLOCKED', 'error': str(error)}
    checks['gpu_9b'] = {'status': 'BLOCKED', 'reason': 'Requires CUDA and >=14 GiB total VRAM with sufficient free memory'}
    if 'torch' in imported and imported['torch'].cuda.is_available():
        free, total = imported['torch'].cuda.mem_get_info()
        checks['gpu_9b'] = {'status': 'PASS' if total >= 14*2**30 and free >= 12*2**30 else 'BLOCKED',
                            'free_bytes': free, 'total_bytes': total}
    checks['peft_checkpoint_roundtrip'] = {'status':'BLOCKED','reason':'Requires importable torch, transformers, peft and safetensors'}
    if all(name in imported for name in ('torch','transformers','peft','safetensors')):
        try:
            import torch
            from transformers import LlamaConfig,LlamaForCausalLM
            from peft import LoraConfig,get_peft_model,PeftModel,get_peft_model_state_dict
            config=LlamaConfig(vocab_size=64,hidden_size=16,intermediate_size=32,
                               num_hidden_layers=1,num_attention_heads=2,num_key_value_heads=2)
            tiny=get_peft_model(LlamaForCausalLM(config),LoraConfig(r=2,lora_alpha=4,
                target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
            tiny.save_pretrained(output/'tiny_untrained_adapter')
            reloaded=PeftModel.from_pretrained(LlamaForCausalLM(config),str(output/'tiny_untrained_adapter'),local_files_only=True)
            original_state=get_peft_model_state_dict(tiny)
            restored_state=get_peft_model_state_dict(reloaded)
            assert original_state.keys()==restored_state.keys()
            assert all(torch.equal(value,restored_state[key]) for key,value in original_state.items())
            checks['peft_checkpoint_roundtrip']={'status':'PASS',
                'scope':'Tiny random CPU Llama adapter save/reload only; no optimizer, no Qwen checkpoint'}
        except Exception as error:
            checks['peft_checkpoint_roundtrip']={'status':'BLOCKED','error':str(error)}
    ast.parse((ROOT/'scripts/finetune.py').read_text(encoding='utf-8'))
    checks['training_script_syntax'] = {'status': 'PASS'}
    report['limitations'] = ['No model weights loaded; Qwen forward/backward and actual PEFT checkpoint remain unverified.',
        'Filesystem checkpoint test is not a model checkpoint test.',
        'Dataset curation and licensing/human acceptance remain separate requirements.']
    report['ready_for_9b_qlora'] = all(check['status']=='PASS' for check in checks.values())
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    for name, check in checks.items():
        print(name, check['status'])
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', default='models/Qwen3.5-9B')
    parser.add_argument('--train', default='outputs/v2_3/sft_candidate/train.jsonl')
    parser.add_argument('--valid', default='outputs/v2_3/sft_candidate/validation.jsonl')
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-length', type=int, default=1024)
    args = parser.parse_args()
    if args.max_length <= 0:
        parser.error('max-length must be positive')
    report = run_preflight(args.model, args.train, args.valid, args.output, args.max_length)
    return 0 if report['ready_for_9b_qlora'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
