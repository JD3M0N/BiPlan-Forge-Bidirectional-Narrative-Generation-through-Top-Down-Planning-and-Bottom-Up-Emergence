<#
.SYNOPSIS
    Puerta de calidad local: las mismas comprobaciones que .github/workflows/quality.yml.

.DESCRIPTION
    Ejecuta las cinco comprobaciones desde la raíz del repositorio y no corta en el primer
    fallo, para que una sola vuelta enseñe todo el daño. Devuelve 0 sólo si todas pasan.

.PARAMETER Fast
    Lanza únicamente pytest, para el bucle de iteración rápida.

.EXAMPLE
    .\quality.ps1
    .\quality.ps1 -Fast
#>
[CmdletBinding()]
param(
    [switch]$Fast
)

$ErrorActionPreference = "Continue"

# tests/test_source_documentation.py resuelve su glob contra el directorio de trabajo y pasa
# en vacío desde cualquier otro sitio, así que la raíz no es opcional.
Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
    Write-Host "Aviso: no encontré .venv, uso el python del PATH." -ForegroundColor Yellow
}

$failed = New-Object System.Collections.Generic.List[string]

function Invoke-Check {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Body
    )
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    & $Body
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        $script:failed.Add($Name)
        Write-Host "$Name : FALLO (código $code)" -ForegroundColor Red
    }
    else {
        Write-Host "$Name : OK" -ForegroundColor Green
    }
}

if (-not $Fast) {
    Invoke-Check "ruff check" { & $python -m ruff check . }
    Invoke-Check "ruff format --check" { & $python -m ruff format --check . }
}

Invoke-Check "pytest" { & $python -m pytest -q -p no:cacheprovider }

if (-not $Fast) {
    Invoke-Check "pip check" { & $python -m pip check }
    # pytest no lo recoge (python_files = ["test_*.py"]) y exige Windows PowerShell 5.1.
    Invoke-Check "sync-railway-stories" {
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'tests\test_sync_railway_stories.ps1'
    }
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host ("Fallaron " + $failed.Count + ": " + ($failed -join ", ")) -ForegroundColor Red
    exit 1
}
Write-Host "Puerta de calidad limpia." -ForegroundColor Green
exit 0
