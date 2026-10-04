<#
.SYNOPSIS
    Corre toda la suite de pytest de una vez, con salida compacta.

.DESCRIPTION
    Es el único comando para correr los tests de este repositorio: local, en
    `quality.ps1` y en CI. Fija el temporal de pytest en `%TEMP%\asg-pytest-tmp`,
    porque el `pytest-of-<usuario>` por defecto falla con PermissionError en
    algunos entornos de sandbox; si ese directorio no se puede escribir, usa
    `.cache\pytest-tmp`. El `conftest.py` de la raíz anula `os.fsync`, que en el
    disco del repositorio cuesta ~125 ms por escritura. Filtra las líneas de
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

function Test-WritableDirectory([string]$Path) {
    try {
        New-Item -ItemType Directory -Force -Path $Path -ErrorAction Stop | Out-Null
        $probe = Join-Path $Path ".probe"
        Set-Content -LiteralPath $probe -Value "" -ErrorAction Stop
        Remove-Item -LiteralPath $probe -Force -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

$basetemp = Join-Path ([System.IO.Path]::GetTempPath()) "asg-pytest-tmp"
if (-not (Test-WritableDirectory $basetemp)) {
    $basetemp = Join-Path $PSScriptRoot ".cache\pytest-tmp"
    New-Item -ItemType Directory -Force -Path $basetemp | Out-Null
}

$progressLine = '^[\.sxXFE]+\s*(\[\s*\d+%\])?\s*$'

$args = @("-m", "pytest", "-q", "--tb=short", "-rfE", "--basetemp=$basetemp") + $PytestArgs

& $python @args 2>&1 | ForEach-Object {
    if ($_ -notmatch $progressLine) {
        Write-Host $_
    }
}
exit $LASTEXITCODE
