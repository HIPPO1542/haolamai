"""Shared pretokenization and loss-mask contract for preflight and real training."""
import json
import hashlib
from pathlib import Path
import sys

MODEL_ID='Qwen/Qwen3.5-9B'
LORA_TARGETS=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']


def sft_data_options(max_length):
    return {'max_length':max_length,'completion_only_loss':True,'packing':False,
            'dataset_kwargs':{'skip_prepare_dataset':True},'remove_unused_columns':False,
            'gradient_checkpointing':True,'optim':'adamw_torch'}


def validate_launch_report(report_path,model,train,validation,max_length):
    report=json.loads(Path(report_path).read_text(encoding='utf-8'))
    required=('host_resources','dataset_format_split','full_library_imports','model_id_config','weight_files',
              'gpu_9b','tokenizer_tokens_truncation','actual_loss_collator','qlora_config')
    blocked=[name for name in required if report.get('checks',{}).get(name,{}).get('status')!='PASS']
    if blocked:raise ValueError('Preflight launch checks remain blocked: '+', '.join(blocked))
    if report.get('model_id')!=MODEL_ID or Path(report.get('model_path','')).resolve()!=Path(model).resolve():
        raise ValueError('Preflight model identity/path mismatch')
    if Path(report['python']).resolve()!=Path(sys.executable).resolve():raise ValueError('Use the same interpreter that ran preflight')
    if report['checks']['tokenizer_tokens_truncation']['max_length']!=max_length:raise ValueError('Preflight max-length differs')
    hashes={'train':hashlib.sha256(Path(train).read_bytes()).hexdigest(),
            'validation':hashlib.sha256(Path(validation).read_bytes()).hexdigest()}
    if hashes!=report.get('dataset_sha256'):raise ValueError('Dataset changed after preflight')
    return report


def validate_resume_checkpoint(path):
    path=Path(path).resolve()
    for name in ('trainer_state.json','optimizer.pt','scheduler.pt','adapter_config.json','rng_state.pth'):
        if not (path/name).is_file():raise ValueError('Resume checkpoint missing '+name)
    if not (path/'adapter_model.safetensors').is_file():raise ValueError('Resume checkpoint lacks adapter tensors')
    state=json.loads((path/'trainer_state.json').read_text(encoding='utf-8'))
    if not isinstance(state.get('global_step'),int) or state['global_step']<=0:
        raise ValueError('Resume needs a real completed training-step checkpoint, not a config-only save')
    return str(path)


def validate_9b_config(path):
    config=json.loads((Path(path)/'config.json').read_text(encoding='utf-8'))
    text=config.get('text_config',config)
    if text.get('model_type')!='qwen3_5_text':raise ValueError('Expected Qwen3.5 text backbone config')
    expected={'hidden_size':4096,'num_hidden_layers':32,'intermediate_size':12288,
              'num_attention_heads':16,'num_key_value_heads':4}
    if any(text.get(key)!=value for key,value in expected.items()):
        raise ValueError('Config does not match the intended Qwen3.5-9B dimensions; no model substitution')
    manifest=Path(path)/'myai_download_manifest.json'
    if manifest.is_file() and json.loads(manifest.read_text())['model_id']!=MODEL_ID:
        raise ValueError('Download manifest is for a different model')
    return text


def load_text_config(path):
    from transformers import Qwen3_5TextConfig
    return Qwen3_5TextConfig(**validate_9b_config(path))


def tokenize_example(tokenizer,row,max_length):
    prompt=tokenizer.apply_chat_template(row['prompt'],tokenize=True,return_dict=False,
        add_generation_prompt=True,enable_thinking=False)
    full=tokenizer.apply_chat_template(row['prompt']+row['completion'],tokenize=True,return_dict=False,
        add_generation_prompt=False,enable_thinking=False)
    if full[:len(prompt)]!=prompt:
        raise ValueError('Chat template prompt is not a token prefix of full conversation; inspect thinking/template settings')
    input_ids=full[:max_length]
    completion_mask=[int(index>=len(prompt)) for index in range(len(input_ids))]
    labels=[token if mask else -100 for token,mask in zip(input_ids,completion_mask)]
    stats={'full_tokens':len(full),'prompt_tokens':len(prompt),'completion_tokens':len(full)-len(prompt),
        'retained_completion_tokens':sum(completion_mask),'completion_truncated':len(full)>max_length,
        'completion_lost':not any(completion_mask)}
    return {'input_ids':input_ids,'labels':labels,'completion_mask':completion_mask},stats


def completion_collator(tokenizer):
    from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
    import inspect
    parameters=inspect.signature(DataCollatorForLanguageModeling).parameters
    kwargs={'pad_token_id':tokenizer.pad_token_id}
    if 'completion_only_loss' in parameters:kwargs['completion_only_loss']=True
    collator=DataCollatorForLanguageModeling(**kwargs)
    examples=[{'input_ids':[11,12,13],'labels':[-100,-100,13],'completion_mask':[0,0,1]},
              {'input_ids':[11,14],'labels':[-100,14],'completion_mask':[0,1]}]
    batch=collator(examples)
    actual=batch['labels'].tolist()
    if actual!=[[-100,-100,13],[-100,14,-100]]:
        raise ValueError('Installed TRL collator did not preserve prompt/padding loss masks')
    return collator
