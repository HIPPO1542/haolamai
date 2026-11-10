param(
  [ValidateSet('high','balanced')][string]$Profile = 'high',
  [double]$Epochs = 1.0,
  [int]$MaxLength = 384
)
$ErrorActionPreference = 'Stop'
$project = (Get-Location).Path
if (-not (Test-Path '.\scripts\finetune.py')) {
  throw 'Hay chay PowerShell tu thu muc goc MyAI_v0_3_Windows!'
}
$pack = Split-Path -Parent $PSScriptRoot
$train = Join-Path $pack '03_sft_addon\myai_sft_addon_train.jsonl'
$valid = Join-Path $pack '03_sft_addon\myai_sft_addon_validation.jsonl'
if (-not (Test-Path $train) -or -not (Test-Path $valid)) {throw 'Khong tim thay du lieu SFT bo sung.'}
$size = if ($Profile -eq 'high') {'9B'} else {'4B'}
$model = "models/Qwen3.5-$size"
$output = "adapters/myai-sales-prepared-$size"
if (-not (Test-Path (Join-Path $model 'config.json'))) {throw "Chua tai model $model"}
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:WANDB_DISABLED='true'
Write-Host "Train supplement data ONLY (khong ghi de data/train.jsonl): $train"
& '.\.venv\Scripts\python.exe' -m scripts.finetune --model $model --output $output --train $train --valid $valid --method qlora --epochs $Epochs --max-length $MaxLength --batch-size 1 --accumulation 8
if ($LASTEXITCODE -ne 0) {throw 'Train failed; inspect log before renting more GPU time.'}
Write-Host "Adapter saved: $output"
Write-Warning 'De app su dung adapter moi, cap nhat MYAI_ADAPTER khi chay uvicorn truc tiep. Khong duoc danh gia bang test bi train tron vao.'
