param([ValidateSet("high", "balanced")][string]$Profile = "high")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot 'python.ps1')
$pythonExe = Resolve-MyAIPython -Capability qwen
$size = if ($Profile -eq "high") { "9B" } else { "4B" }
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
& $pythonExe -m scripts.evaluate_adapter --model "models/Qwen3.5-$size" --adapter "adapters/myai-sales-v0.3-$size"
if ($LASTEXITCODE -ne 0) { throw "Model evaluation failed; inspect data/evaluation.json" }
