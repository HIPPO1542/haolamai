"""Real QLoRA/LoRA supervised fine-tuning; no model simulation or hosted API.

Requires a previously downloaded local Qwen model and CUDA-capable GPU for QLoRA.
"""
import argparse
import json
import os
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description='Fine-tune Qwen for Vietnamese multi-sector sales')
    p.add_argument('--model',default='models/Qwen3.5-9B')
    p.add_argument('--output',default='adapters/myai-sales-v0.3-9B')
    p.add_argument('--train',default='private_data/myai-v24/train.jsonl')
    p.add_argument('--valid',default='private_data/myai-v24/validation.jsonl')
    p.add_argument('--heldout',help='Additional SFT test JSONL to check for contamination; never trained')
    p.add_argument('--method',choices=['qlora','lora'],default='qlora')
    p.add_argument('--epochs',type=float,default=2.0)
    p.add_argument('--max-length',type=int,default=2048)
    p.add_argument('--batch-size',type=int,default=1)
    p.add_argument('--accumulation',type=int,default=8)
    p.add_argument('--lr',type=float,default=1.5e-4)
    p.add_argument('--preflight-only', action='store_true', help='Check readiness without starting training')
    p.add_argument('--preflight-output', help='New preflight directory under outputs')
    p.add_argument('--run-preflight', action='store_true', help='Run mandatory launch checks immediately before approved training')
    p.add_argument('--preflight-report', help='Verified v2.4 report from this interpreter and these exact data files')
    p.add_argument('--accept-reviewed-candidate',action='store_true',help='Explicit operator acknowledgment after reviewing candidate/privacy/rights')
    p.add_argument('--resume-from-checkpoint',help='Read an existing checkpoint and save future checkpoints to a new output directory')
    args=p.parse_args()
    if args.max_length <= 0 or args.batch_size <= 0 or args.accumulation <= 0 or args.epochs <= 0:
        p.error('max-length, batch-size, accumulation and epochs must be positive')
    if args.preflight_only:
        if not args.preflight_output:
            p.error('--preflight-only requires --preflight-output')
        from scripts.qwen_preflight_v24 import run_preflight
        report = run_preflight(args.model, args.train, args.valid, args.preflight_output, args.max_length)
        return 0 if report['technical_launch_checks_pass'] else 2
    if args.run_preflight:
        if not args.preflight_output or not args.accept_reviewed_candidate:
            p.error('--run-preflight needs --preflight-output and --accept-reviewed-candidate after data review')
        from scripts.training_data_guard import validate_training_inputs
        validate_training_inputs(args.train, args.valid, args.heldout)
        from scripts.qwen_preflight_v24 import run_preflight
        report = run_preflight(args.model, args.train, args.valid, args.preflight_output, args.max_length)
        if not report['technical_launch_checks_pass']:
            raise SystemExit('Preflight BLOCKED. See report.json; training was not started.')
        args.preflight_report = str(Path(args.preflight_output)/'report.json')
    if not args.preflight_report or not args.accept_reviewed_candidate:
        p.error('Training requires --preflight-report and --accept-reviewed-candidate; preflight-only never trains')
    from scripts.qwen_training_contract import (validate_launch_report,validate_resume_checkpoint,
        load_text_config,tokenize_example,completion_collator,sft_data_options,LORA_TARGETS)
    validate_launch_report(args.preflight_report,args.model,args.train,args.valid,args.max_length)
    resume=validate_resume_checkpoint(args.resume_from_checkpoint) if args.resume_from_checkpoint else None
    os.environ['WANDB_DISABLED']='true'
    os.environ.setdefault('HF_HUB_OFFLINE','1')
    os.environ.setdefault('TRANSFORMERS_OFFLINE','1')
    os.environ['TOKENIZERS_PARALLELISM']='false'
    if not (Path(args.model)/'config.json').is_file():
        raise SystemExit('Missing local model. Run scripts.download_model first.')
    for path in (args.train,args.valid):
        if not Path(path).is_file():raise SystemExit('Missing training data: '+path)
    from scripts.training_data_guard import validate_training_inputs
    validate_training_inputs(args.train, args.valid, args.heldout)
    if Path(args.output).exists() and any(Path(args.output).iterdir()):
        raise SystemExit('Adapter output is not empty; choose a new output directory.')

    import torch
    from datasets import Dataset
    from peft import LoraConfig,prepare_model_for_kbit_training
    from transformers import AutoTokenizer,Qwen3_5ForCausalLM,BitsAndBytesConfig
    from trl import SFTConfig,SFTTrainer

    if args.method=='qlora' and not torch.cuda.is_available():
        raise RuntimeError('QLoRA needs NVIDIA CUDA. On Windows install CUDA-enabled PyTorch and bitsandbytes; Ubuntu/WSL is NOT required.')
    if torch.cuda.is_available():
        free,total=torch.cuda.mem_get_info()
        print(f'GPU: {torch.cuda.get_device_name()} | Free VRAM: {free/2**30:.2f}GB / {total/2**30:.2f}GB')
        size = '9B' if '9B' in args.model else ('4B' if '4B' in args.model else '?')
        if size == '9B' and total < 14 * 2**30:
            raise RuntimeError('9B requires substantial VRAM for QLoRA; select 4B explicitly or use a GPU with >=14 GiB and headroom. No silent downgrade.')
        if size == '4B' and total < 8 * 2**30:
            raise RuntimeError('4B QLoRA usually needs >=8 GiB VRAM. This machine may not be suitable for the requested models.')
        if free<4*2**30:
            print('WARNING: less than 4 GB free VRAM; close GPU workloads or use a shorter max-length.')
    dtype=(torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
        else torch.float16 if torch.cuda.is_available() else torch.float32)
    quant=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
        bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype) if args.method=='qlora' else None
    tokenizer=AutoTokenizer.from_pretrained(args.model,local_files_only=True)
    if tokenizer.pad_token is None:tokenizer.pad_token=tokenizer.eos_token
    kwargs={'local_files_only':True,'dtype':dtype}
    if quant:
        kwargs.update(quantization_config=quant,device_map={'':torch.cuda.current_device()})
    model=Qwen3_5ForCausalLM.from_pretrained(args.model,config=load_text_config(args.model),**kwargs)
    model.config.use_cache=False
    if quant:
        model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    ds={}
    collator=completion_collator(tokenizer)
    for split,path in [('train',args.train),('validation',args.valid)]:
        prepared=[]
        with open(path,encoding='utf-8-sig') as stream:
            for line in stream:
                if not line.strip():continue
                example,statistics=tokenize_example(tokenizer,json.loads(line),args.max_length)
                if statistics['completion_truncated'] or statistics['completion_lost']:
                    raise RuntimeError('Completion truncation/loss detected; rerun tokenizer preflight with a measured safe length')
                prepared.append(example)
        ds[split]=Dataset.from_list(prepared)
    if len(ds['train'])<100:
        raise RuntimeError('Too little training data. At least 100 samples required for this pipeline test.')
    lora=LoraConfig(r=16,lora_alpha=32,lora_dropout=0.05,bias='none',
        target_modules=LORA_TARGETS,
        task_type='CAUSAL_LM')
    cfg=SFTConfig(output_dir=args.output,num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,per_device_eval_batch_size=1,
        gradient_accumulation_steps=args.accumulation,
        learning_rate=args.lr,lr_scheduler_type='cosine',warmup_ratio=0.05,
        **sft_data_options(args.max_length),
        bf16=(dtype==torch.bfloat16),fp16=(dtype==torch.float16),
        eval_strategy='epoch',save_strategy='epoch',save_total_limit=None,save_only_model=False,save_safetensors=True,
        logging_steps=10,report_to='none',seed=42,
        dataloader_num_workers=0)
    trainer=SFTTrainer(model=model,args=cfg,train_dataset=ds['train'],
        eval_dataset=ds['validation'],peft_config=lora,processing_class=tokenizer,data_collator=collator)
    train_result=trainer.train(resume_from_checkpoint=resume)
    trainer.save_model(args.output)
    tokenizer.save_pretrained(args.output)
    manifest={
        'base_model_path':str(Path(args.model).resolve()),
        'training_samples':len(ds['train']),
        'validation_samples':len(ds['validation']),
        'method':args.method,'epochs':args.epochs,'max_length':args.max_length,
        'train_loss':float(train_result.training_loss),
        'cuda_gpu':torch.cuda.get_device_name() if torch.cuda.is_available() else None,
        'warning':'Synthetic training data is not evidence of production quality.'
    }
    with open(Path(args.output)/'myai_training_manifest.json','w',encoding='utf-8') as f:
        json.dump(manifest,f,indent=2,ensure_ascii=False)
    print('REAL adapter trained and saved to',args.output)

if __name__=='__main__':raise SystemExit(main())
