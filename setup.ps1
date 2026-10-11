<#
.SYNOPSIS
    Crea o sincroniza un entorno Python 3.12 o 3.15 y comprueba sus dependencias.
.DESCRIPTION
    Cada version tiene su archivo de restricciones comprobado (constraints-py312.txt y
    constraints-py315.txt). Los requirements*.txt citan el de 3.12; con 3.15 se instala una
    copia temporal que cita el suyo. Sin -Python se prefiere 3.12 y, si falta, 3.15.
.EXAMPLE
    .\setup.ps1 -Telegram
.EXAMPLE
    .\setup.ps1 -Python C:\Python315\python.exe
#>
[CmdletBinding()]
param(
    [switch]$Telegram,
    [string]$Python,
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"
$Supported = @("3.12", "3.15")
Push-Location -LiteralPath $PSScriptRoot
try {
    $envDirectory = if ([System.IO.Path]::IsPathRooted($VenvPath)) {
        [System.IO.Path]::GetFullPath($VenvPath)
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $VenvPath))
    }
    $envPython = Join-Path $envDirectory "Scripts\python.exe"
    # Single quotes only: Windows PowerShell 5.1 drops double quotes in native arguments.
    $versionCheck = "import sys; v = '%d.%d' % sys.version_info[:2]; print(v); sys.exit(0 if v in ('3.12', '3.15') and sys.maxsize > 2**32 else 1)"

    if (-not (Test-Path -LiteralPath $envPython)) {
        if (Test-Path -LiteralPath $envDirectory) {
            throw "El directorio $envDirectory ya existe pero no tiene Python. Usa una carpeta nueva para -VenvPath."
        }
        $pythonArgs = @()
        if (-not $Python) {
            $Python = "python"
            if (Get-Command py -ErrorAction SilentlyContinue) {
                foreach ($candidate in $Supported) {
                    $ErrorActionPreference = "Continue"
                    & py "-$candidate" -c "pass" 2>$null
                    $found = $LASTEXITCODE -eq 0
                    $ErrorActionPreference = "Stop"
                    if ($found) { $Python = "py"; $pythonArgs = @("-$candidate"); break }
                }
            }
        }
        & $Python @pythonArgs -c $versionCheck | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Instala Python 3.12 o 3.15 de 64 bits o indica su ruta con -Python." }
        & $Python @pythonArgs -m venv $envDirectory
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
    }

    $version = (& $envPython -c $versionCheck | Select-Object -Last 1)
    if ($LASTEXITCODE -ne 0) { throw "El entorno debe usar Python 3.12 o 3.15 de 64 bits. Recrealo en una carpeta nueva." }
    $requirements = if ($Telegram) { "requirements-telegram.txt" } else { "requirements-dev.txt" }
    $constraints = "constraints-py$($version.Trim().Replace('.', '')).txt"
    $generated = $null
    if ($constraints -ne "constraints-py312.txt") {
        # The checked-in requirements pin 3.12; a sibling copy keeps their relative paths valid.
        $generated = Join-Path $PSScriptRoot ".requirements-setup.txt"
        $lines = foreach ($line in [IO.File]::ReadAllLines((Join-Path $PSScriptRoot $requirements))) {
            if ($line -match '^-r\s+(.+)$') {
                [IO.File]::ReadAllLines((Join-Path $PSScriptRoot $Matches[1].Trim()))
            } else {
                $line
            }
        }
        $lines = $lines | ForEach-Object { $_ -replace '^-c\s+constraints-py\d+\.txt$', "-c $constraints" }
        [IO.File]::WriteAllLines($generated, [string[]]$lines, [Text.UTF8Encoding]::new($false))
        $requirements = $generated
    }
    Write-Host "Python $($version.Trim()) con $constraints"
    try {
        & $envPython -m pip --disable-pip-version-check install -r $requirements
        if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de dependencias; revisa la salida de pip." }
    } finally {
        if ($generated) { Remove-Item -LiteralPath $generated -Force -ErrorAction SilentlyContinue }
    }
    & $envPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Hay dependencias incompatibles." }
    & $envPython -m asg_telegram.app --help
    if ($LASTEXITCODE -ne 0) { throw "No se pudo cargar el bot." }

    # find_project_root necesita Stories incluso en un clon nuevo (Git la ignora).
    New-Item -ItemType Directory -Force -Path "Stories", "Evaluations" | Out-Null
    if (-not (Test-Path -LiteralPath ".env")) {
        Copy-Item -LiteralPath ".env.example" -Destination ".env"
    }
    Write-Host "Entorno listo: $envPython" -ForegroundColor Green
    Write-Host "Configura .env y la base del estudio antes de arrancar el bot. Consulta apps/telegram/DEPLOYMENT.md."
} finally {
    Pop-Location
}
