<#
.SYNOPSIS
    Puerta de calidad local: las mismas comprobaciones que .github/workflows/quality.yml.

.DESCRIPTION
    Ejecuta las cuatro comprobaciones desde la raíz del repositorio y no corta en el primer
    fallo, para que una sola vuelta enseñe todo el daño. Devuelve 0 sólo si todas pasan.
    El paso de tests delega en run-tests.ps1, que es el único comando para correrlos: aquí y
    en CI corren exactamente lo mismo.

.PARAMETER Fast
    Lanza únicamente run-tests.ps1, para el bucle de iteración rápida.

.EXAMPLE
    .\quality.ps1
    .\quality.ps1 -Fast
#>
[CmdletBinding()]
param(
    [switch]$Fast
)

$ErrorActionPreference = "Continue"

# tests/test_source_documentation.py resuelve su glob desde Path(__file__), así que ya no
# necesita correr desde la raíz para pasar, pero el resto de rutas relativas del repo sí.
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

Invoke-Check "run-tests" { & (Join-Path $PSScriptRoot "run-tests.ps1") }

if (-not $Fast) {
    Invoke-Check "pip check" { & $python -m pip check }
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host ("Fallaron " + $failed.Count + ": " + ($failed -join ", ")) -ForegroundColor Red
    exit 1
}
Write-Host "Puerta de calidad limpia." -ForegroundColor Green
exit 0
