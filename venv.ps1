$ErrorActionPreference = "Stop"

$activateScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"

if (-not (Test-Path -LiteralPath $activateScript)) {
    Write-Error "No se encontró .venv. Créalo e instala las dependencias antes de activarlo."
    exit 1
}

. $activateScript
