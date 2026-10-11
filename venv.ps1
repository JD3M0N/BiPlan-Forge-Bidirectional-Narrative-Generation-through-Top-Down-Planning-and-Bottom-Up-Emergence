$ErrorActionPreference = "Stop"

$activateScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"

if (-not (Test-Path -LiteralPath $activateScript)) {
    Write-Error "No se encontro .venv. Ejecuta .\setup.ps1 (desarrollo) o .\setup.ps1 -Telegram (bot)."
    exit 1
}

. $activateScript
