# Explicit prepared dataset runner. Never calls scripts.make_train_data.
param(
 [string]$Model = "models/Qwen3.5-9B",
 [string]$Output = "adapters/myai-sales-v0.4-9B",
 [double]$Epochs = 1,
 [int]$MaxLength = 1024
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Missing .venv\Scripts\python.exe' }
if (-not (Test-Path '.\data\prepared_v2\train.jsonl')) { throw 'Missing prepared_v2 training data' }
if (-not (Test-Path '.\data\prepared_v2\validation.jsonl')) { throw 'Missing prepared_v2 validation data' }
& $Python .\MyAI_Prepare_Datasets_v2\verify_v2.py --project-root .
if ($LASTEXITCODE -ne 0) { throw 'Data verification failed' }
& $Python -m scripts.finetune --model $Model --output $Output --train 'data/prepared_v2/train.jsonl' --valid 'data/prepared_v2/validation.jsonl' --method qlora --epochs $Epochs --max-length $MaxLength --batch-size 1 --accumulation 8
if ($LASTEXITCODE -ne 0) { throw 'Training failed. Check log / GPU VRAM' }
