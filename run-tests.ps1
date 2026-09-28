<#
.SYNOPSIS
    Corre toda la suite de pytest de una vez, con salida compacta.

.DESCRIPTION
    Es el único comando para correr los tests de este repositorio: local, en
    `quality.ps1` y en CI. Redirige el temporal de pytest al `.cache` del
    repositorio, porque el temporal por defecto de Windows falla con
    PermissionError en algunos entornos de sandbox. Filtra las líneas de
    progreso ("....F..  [ 42%]") para que una vuelta limpia quede en una sola
    línea; si algo falla, se quedan los FAILED y sus tracebacks cortos.

.EXAMPLE
    .\run-tests.ps1
    .\run-tests.ps1 -- packages/stagecraft/tests -k revision
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

Set-Location -LiteralPath $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
    Write-Host "Aviso: no encontré .venv, uso el python del PATH." -ForegroundColor Yellow
}

$basetemp = Join-Path $PSScriptRoot ".cache\pytest-tmp"
New-Item -ItemType Directory -Force -Path $basetemp | Out-Null

$progressLine = '^[\.sxXFE]+\s*(\[\s*\d+%\])?\s*$'

$args = @("-m", "pytest", "-q", "--tb=short", "-rfE", "--basetemp=$basetemp") + $PytestArgs

& $python @args 2>&1 | ForEach-Object {
    if ($_ -notmatch $progressLine) {
        Write-Host $_
    }
}
exit $LASTEXITCODE
