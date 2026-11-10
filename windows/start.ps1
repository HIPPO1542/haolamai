param(
  [ValidateSet("high", "balanced")][string]$Profile = "high",
  [switch]$SearchOnly
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot 'python.ps1')
$pythonExe = Resolve-MyAIPython
$size = if ($Profile -eq "high") { "9B" } else { "4B" }
$env:MYAI_MODEL = (Join-Path (Get-Location) "models/Qwen3.5-$size")
$env:MYAI_ADAPTER = (Join-Path (Get-Location) "adapters/myai-sales-v0.3-$size")
$env:MYAI_INFER_4BIT = "1"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
if (-not $SearchOnly) {
  if (!(Test-Path (Join-Path $env:MYAI_MODEL "config.json"))) { throw "Missing model: $env:MYAI_MODEL. Run windows/download.ps1 first." }
  if (!(Test-Path (Join-Path $env:MYAI_ADAPTER "adapter_config.json"))) { throw "Missing trained adapter: $env:MYAI_ADAPTER. Run windows/train.ps1 first." }
}
& $pythonExe -m uvicorn myai.api:app --host 127.0.0.1 --port 8000
if ($LASTEXITCODE -ne 0) { throw "API failed; inspect the server log." }
