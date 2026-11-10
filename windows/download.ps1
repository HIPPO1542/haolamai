param([ValidateSet("high", "balanced")][string]$Profile = "high")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot 'python.ps1')
$pythonExe = Resolve-MyAIPython -Capability hub
$size = if ($Profile -eq "high") { "9B" } else { "4B" }
& $pythonExe -m scripts.download_model --model "Qwen/Qwen3.5-$size" --output "models/Qwen3.5-$size"
if ($LASTEXITCODE -ne 0) { throw "Download failed" }
