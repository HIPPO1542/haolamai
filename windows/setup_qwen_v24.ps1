param(
    [Parameter(Mandatory=$true)][string]$BasePython,
    [string]$EnvironmentPath='.venv',
    [string]$ReportDirectory='outputs/qwen_setup_v24',
    [string]$Wheelhouse,
    [switch]$Install
)
$ErrorActionPreference='Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
$setupArguments=@('-m','scripts.setup_qwen_environment','--base-python',$BasePython,'--environment',$EnvironmentPath,'--report-dir',$ReportDirectory)
if($Wheelhouse){$setupArguments+=@('--wheelhouse',$Wheelhouse)}
if($Install){$setupArguments+='--install'}
& $BasePython @setupArguments
if($LASTEXITCODE -ne 0){throw 'Qwen setup remains blocked. Inspect reports; old environments were preserved.'}
