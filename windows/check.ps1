$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
. (Join-Path $PSScriptRoot 'python.ps1')
$pythonExe = Resolve-MyAIPython
nvidia-smi
if ($LASTEXITCODE -ne 0) { throw "nvidia-smi khong chay duoc. Kiem tra NVIDIA driver." }
& $pythonExe -m scripts.preflight
if ($LASTEXITCODE -ne 0) { throw 'Qwen environment preflight has unresolved checks. Read the report.' }
