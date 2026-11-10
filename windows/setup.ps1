param(
  [string]$CudaIndex = "https://download.pytorch.org/whl/cu132",
  [string]$EnvironmentPath = '.venv'
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (Test-Path -LiteralPath $EnvironmentPath) { throw 'Environment already exists. Choose a new path; old environments will not be overwritten.' }
$environmentTarget = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $EnvironmentPath))
$workspacePrefix = (Get-Location).Path.TrimEnd('\') + '\'
if (-not $environmentTarget.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Environment must be inside the workspace.' }
py -3.11 -m venv $environmentTarget
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 is inaccessible. No existing environment was removed.' }
$py = Join-Path $environmentTarget "Scripts\python.exe"
if (!(Test-Path $py)) { throw "Khong tao duoc .venv. Cai Python 3.11 64-bit va thu lai." }
& $py -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $py -m pip install torch torchvision --index-url $CudaIndex
if ($LASTEXITCODE -ne 0) { throw "PyTorch CUDA install failed. Chon URL phu hop tai pytorch.org/get-started/locally/" }
& $py -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Package install failed" }
& $py -m scripts.preflight
if ($LASTEXITCODE -ne 0) { throw "Preflight failed" }
