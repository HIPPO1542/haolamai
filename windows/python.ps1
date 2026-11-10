function Resolve-MyAIPython {
    param([string]$ExplicitPath = $env:MYAI_PYTHON,
          [ValidateSet('backend','qwen','hub')][string]$Capability='backend')
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $candidates = if ($ExplicitPath) { @($ExplicitPath) } else {
        @('.venv/Scripts/python.exe')
    }
    foreach ($candidate in $candidates) {
        $pythonPath = if ([System.IO.Path]::IsPathRooted($candidate)) { $candidate } else { Join-Path $projectRoot $candidate }
        if (-not (Test-Path -LiteralPath $pythonPath)) { continue }
        $probeCode = switch($Capability) {
            'qwen' { 'import torch,transformers,peft,trl,bitsandbytes,safetensors' }
            'hub' { 'import huggingface_hub' }
            default { 'import fastapi,uvicorn,pydantic' }
        }
        try {
            $probe = & $pythonPath -c $probeCode 2>&1
            if ($LASTEXITCODE -eq 0) { return $pythonPath }
        } catch { continue }
    }
    throw 'No accessible Python interpreter. Set MYAI_PYTHON or create a new environment; preserve the old .venv for diagnosis.'
}
