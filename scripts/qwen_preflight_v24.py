"""Qwen3.5-9B preflight: no training, no smaller-model substitution, no network."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import hashlib

from scripts.qwen_training_contract import MODEL_ID,validate_9b_config,tokenize_example,completion_collator,LORA_TARGETS,sft_data_options
from scripts.training_data_guard import validate_training_inputs

ROOT=Path(__file__).resolve().parents[1]


def memory_bytes():
    try:
        if os.name=='nt':
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(name,ctypes.c_ulonglong) for name in
                    ('total_physical','available_physical','total_pagefile','available_pagefile','total_virtual','available_virtual','extended')]
            status=MemoryStatus();status.length=ctypes.sizeof(status)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):raise OSError('Memory probe failed')
            return status.total_physical,status.available_physical
        page=os.sysconf('SC_PAGE_SIZE')
        return page*os.sysconf('SC_PHYS_PAGES'),page*os.sysconf('SC_AVPHYS_PAGES')
    except (OSError,ValueError,AttributeError):return None,None


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig') as stream:return [json.loads(line) for line in stream if line.strip()]


def run_preflight(model,train,validation,output,max_length=2048):
    output=Path(output).resolve();model=Path(model).resolve()
    if not output.is_relative_to(ROOT/'outputs') or output.exists():raise ValueError('Use a new preflight directory under outputs')
    output.mkdir(parents=True)
    report={'model_id':MODEL_ID,'model_path':str(model),'python':sys.executable,'training_started':False,'paid_resources_used':False,
            'checks':{},'ready_for_training':False,'ready_for_9b_qlora':False}
    checks=report['checks'];total,available=memory_bytes();free_disk=shutil.disk_usage(output).free
    checks['host_resources']={'status':'PASS' if total and total>=32*2**30 and free_disk>=60*2**30 else 'BLOCKED',
        'ram_total_bytes':total,'ram_available_bytes':available,'disk_free_bytes':free_disk,
        'planning_floor':'32 GiB RAM / 60 GiB free workspace disk, not measured peak usage'}
    try:
        validate_training_inputs(train,validation)
        checks['dataset_format_split']={'status':'PASS','train_rows':len(read_rows(train)),'validation_rows':len(read_rows(validation))}
        report['dataset_sha256']={'train':hashlib.sha256(Path(train).read_bytes()).hexdigest(),
                                  'validation':hashlib.sha256(Path(validation).read_bytes()).hexdigest()}
    except Exception as error:checks['dataset_format_split']={'status':'BLOCKED','error':str(error)}
    # Each import probe is isolated so a failed DLL import cannot poison others.
    imports=output/'imports.json'
    probe=subprocess.run([sys.executable,'-m','scripts.diagnose_environment','--output',str(imports)],cwd=ROOT,
                         capture_output=True,text=True,encoding='utf-8')
    (output/'imports.log').write_text(probe.stdout+probe.stderr,encoding='utf-8')
    details=json.loads(imports.read_text(encoding='utf-8'))
    checks['full_library_imports']={'status':'PASS' if details['full_qwen_imports_pass'] else 'BLOCKED','report':'imports.json'}
    try:
        text=validate_9b_config(model)
        checks['model_id_config']={'status':'PASS','class':'Qwen3_5ForCausalLM','text_model_type':text['model_type'],
            'scope':'Config dimensions/provenance only, not loaded model weights'}
    except Exception as error:checks['model_id_config']={'status':'BLOCKED','error':str(error)}
    weights=list(model.glob('*.safetensors'))
    if (model/'model.safetensors.index.json').is_file():
        index=json.loads((model/'model.safetensors.index.json').read_text())
        complete=all((model/name).is_file() for name in set(index['weight_map'].values()))
    else:complete=bool(weights)
    checks['weight_files']={'status':'PASS' if complete else 'BLOCKED','shards_found':len(weights),'scope':'Presence, not tensor loading'}
    atomic=output/'checkpoint_io.tmp'
    with atomic.open('x') as stream:stream.write('preflight');stream.flush();os.fsync(stream.fileno())
    atomic.replace(output/'checkpoint_io.txt')
    checks['checkpoint_filesystem']={'status':'PASS','scope':'Write/fsync/atomic rename/read only; no model checkpoint'}
    checks['gpu_9b']={'status':'BLOCKED','reason':'CUDA imports unavailable or insufficient VRAM'}
    if details['probes']['torch']['status']=='PASS':
        import torch
        if torch.cuda.is_available():
            free,total_vram=torch.cuda.mem_get_info()
            checks['gpu_9b']={'status':'PASS' if total_vram>=14*2**30 and free>=12*2**30 else 'BLOCKED',
                'gpu':torch.cuda.get_device_name(),'total_bytes':total_vram,'free_bytes':free,
                'scope':'Configured lower gate; actual 9B peak memory not measured'}
    for name in ('tokenizer_tokens_truncation','actual_loss_collator','qlora_config','torch_checkpoint','qwen_adapter_roundtrip'):
        checks[name]={'status':'BLOCKED','reason':'Required Qwen files/imports not available'}
    if details['probes']['transformers']['status']=='PASS' and (model/'tokenizer.json').is_file():
        try:
            from transformers import AutoTokenizer
            tokenizer=AutoTokenizer.from_pretrained(str(model),local_files_only=True)
            if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
            splits={};samples=[]
            for split,path in [('train',train),('validation',validation)]:
                stats=[]
                for row in read_rows(path):
                    example,measure=tokenize_example(tokenizer,row,max_length);stats.append(measure)
                    if len(samples)<2:samples.append(example)
                lengths=sorted(item['full_tokens'] for item in stats)
                splits[split]={'rows':len(stats),'mean_tokens':sum(lengths)/len(lengths),'p95_tokens':lengths[int(.95*len(lengths))],
                    'max_tokens':max(lengths),'completion_cut_rows':sum(item['completion_truncated'] for item in stats),
                    'completion_cut_fraction':sum(item['completion_truncated'] for item in stats)/len(stats),
                    'all_completion_lost_rows':sum(item['completion_lost'] for item in stats)}
            okay=all(not item['completion_cut_rows'] for item in splits.values())
            checks['tokenizer_tokens_truncation']={'status':'PASS' if okay else 'BLOCKED','max_length':max_length,'splits':splits,
                'policy':'Training refuses partial/total completion truncation; adjust length from measured tokens'}
            if details['probes']['trl']['status']=='PASS':
                collator=completion_collator(tokenizer);batch=collator(samples)
                assert all(label==-100 for labels,sample in zip(batch['labels'].tolist(),samples)
                           for label,mask in zip(labels,sample['completion_mask']) if mask==0)
                checks['actual_loss_collator']={'status':'PASS','scope':'Installed TRL collator on real Qwen token IDs; prompt/padding masked'}
        except Exception as error:checks['tokenizer_tokens_truncation']={'status':'BLOCKED','error':str(error)}
    if details['full_qwen_imports_pass']:
        try:
            import torch
            from transformers import BitsAndBytesConfig,Qwen3_5TextConfig,Qwen3_5ForCausalLM
            from peft import LoraConfig,get_peft_model,PeftModel,get_peft_model_state_dict
            from trl import SFTConfig
            from safetensors.torch import save_file,load_file
            quantization=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16)
            lora=LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,target_modules=LORA_TARGETS,task_type='CAUSAL_LM')
            config=SFTConfig(output_dir=str(output/'not_training'),**sft_data_options(max_length),
                report_to='none',use_cpu=True,bf16=False)
            checks['qlora_config']={'status':'PASS','quantization':quantization.to_dict(),'lora':str(lora),
                'gradient_checkpointing':config.gradient_checkpointing,'optimizer':str(config.optim),'scope':'Configuration construction only'}
            tensor=torch.arange(4);torch.save({'probe':tensor},output/'tensor.pt');save_file({'probe':tensor},str(output/'tensor.safetensors'))
            assert torch.equal(torch.load(output/'tensor.pt',weights_only=True)['probe'],load_file(str(output/'tensor.safetensors'))['probe'])
            checks['torch_checkpoint']={'status':'PASS','scope':'Small CPU tensor serializer roundtrip; no training state'}
            # Same Qwen3.5 architecture at diagnostic scale; explicitly NOT the 9B model.
            tiny_config=Qwen3_5TextConfig(vocab_size=64,hidden_size=32,intermediate_size=64,num_hidden_layers=1,
                num_attention_heads=2,num_key_value_heads=2,head_dim=16,layer_types=['full_attention'],
                linear_num_key_heads=2,linear_num_value_heads=2,linear_key_head_dim=16,linear_value_head_dim=16,
                rope_parameters={'rope_type':'default','rope_theta':10000,'mrope_section':[2,1,1],'partial_rotary_factor':.5})
            tiny=get_peft_model(Qwen3_5ForCausalLM(tiny_config),LoraConfig(r=2,target_modules=['q_proj','v_proj'],task_type='CAUSAL_LM'))
            tiny.save_pretrained(output/'untrained_architecture_probe')
            reloaded=PeftModel.from_pretrained(Qwen3_5ForCausalLM(tiny_config),str(output/'untrained_architecture_probe'),local_files_only=True)
            before=get_peft_model_state_dict(tiny);after=get_peft_model_state_dict(reloaded)
            assert before.keys()==after.keys() and all(torch.equal(value,after[key]) for key,value in before.items())
            checks['qwen_adapter_roundtrip']={'status':'PASS','scope':'Untrained diagnostic Qwen architecture only; NOT Qwen3.5-9B checkpoint validation'}
        except Exception as error:checks['qlora_config']={'status':'BLOCKED','error':str(error)}
    checks['target_9b_load_forward_backward']={'status':'BLOCKED','reason':'Not executed: no training authorized; requires actual 9B weights and adequate GPU'}
    checks['resume_after_real_qlora_step']={'status':'BLOCKED','reason':'No real QLoRA step/checkpoint exists; serialization alone does not verify training resume'}
    checks['dataset_human_rights_acceptance']={'status':'BLOCKED','reason':'Candidate provenance and heuristics are not human/rights certification'}
    report['versions']={name:detail.get('status') for name,detail in details['probes'].items()}
    launch_checks=('host_resources','dataset_format_split','full_library_imports','model_id_config','weight_files',
                   'gpu_9b','tokenizer_tokens_truncation','actual_loss_collator','qlora_config','checkpoint_filesystem')
    report['technical_launch_checks_pass']=all(checks[name]['status']=='PASS' for name in launch_checks)
    report['ready_for_training']=all(item['status']=='PASS' for item in checks.values())
    report['ready_for_9b_qlora']=report['ready_for_training']
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    for name,item in checks.items():print(name,item['status'])
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--model',default='models/Qwen3.5-9B')
    parser.add_argument('--train',default='outputs/v2_4/sft_candidate_final/train.jsonl')
    parser.add_argument('--valid',default='outputs/v2_4/sft_candidate_final/validation.jsonl')
    parser.add_argument('--output',required=True);parser.add_argument('--max-length',type=int,default=2048)
    args=parser.parse_args()
    if args.max_length<=0:parser.error('max-length must be positive')
    report=run_preflight(args.model,args.train,args.valid,args.output,args.max_length)
    return 0 if report['technical_launch_checks_pass'] else 2


if __name__=='__main__':raise SystemExit(main())
