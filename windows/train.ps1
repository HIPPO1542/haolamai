param(
  [ValidateSet("high", "balanced")][string]$Profile = "high",
  [double]$Epochs = 2,
  [string]$TrainPath = "private_data/myai-v24/train.jsonl",
  [string]$ValidationPath = "private_data/myai-v24/validation.jsonl",
  [int]$MaxLength = 2048,
  [string]$PreflightReport,
  [switch]$AcceptReviewedCandidate
)
$ErrorActionPreference = "Stop"
if(-not $PreflightReport -or -not $AcceptReviewedCandidate){throw 'Training requires a verified preflight report and explicit candidate review acknowledgment.'}
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot 'python.ps1')
$pythonExe = Resolve-MyAIPython -Capability qwen
$size = if ($Profile -eq "high") { "9B" } else { "4B" }
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:WANDB_DISABLED = "true"
& $pythonExe -m scripts.finetune --model "models/Qwen3.5-$size" --output "adapters/myai-sales-v0.3-$size" --train $TrainPath --valid $ValidationPath --preflight-report $PreflightReport --accept-reviewed-candidate --method qlora --epochs $Epochs --max-length $MaxLength --batch-size 1 --accumulation 8
if ($LASTEXITCODE -ne 0) { throw "QLoRA train failed. Kiem tra VRAM/driver va log." }
