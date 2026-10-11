<#
.SYNOPSIS
    Crea o sincroniza un entorno Python 3.12 y comprueba sus dependencias.
.EXAMPLE
    .\setup.ps1 -Telegram
.EXAMPLE
    .\setup.ps1 -Python C:\Python312\python.exe
#>
[CmdletBinding()]
param(
    [switch]$Telegram,
    [string]$Python,
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"
Push-Location -LiteralPath $PSScriptRoot
try {
    $envDirectory = if ([System.IO.Path]::IsPathRooted($VenvPath)) {
        [System.IO.Path]::GetFullPath($VenvPath)
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot $VenvPath))
    }
    $envPython = Join-Path $envDirectory "Scripts\python.exe"
    $versionCheck = 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 1)'

    if (-not (Test-Path -LiteralPath $envPython)) {
        if (Test-Path -LiteralPath $envDirectory) {
            throw "El directorio $envDirectory ya existe pero no tiene Python. Usa una carpeta nueva para -VenvPath."
        }
        $pythonArgs = @()
        if (-not $Python) {
            if (Get-Command py -ErrorAction SilentlyContinue) {
                $Python = "py"
                $pythonArgs = @("-3.12")
            } else {
                $Python = "python"
            }
        }
        & $Python @pythonArgs -c $versionCheck
        if ($LASTEXITCODE -ne 0) { throw "Instala Python 3.12 de 64 bits o indica su ruta con -Python." }
        & $Python @pythonArgs -m venv $envDirectory
        if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
    }

    & $envPython -c $versionCheck
    if ($LASTEXITCODE -ne 0) { throw "El entorno debe usar Python 3.12 de 64 bits. Recrealo en una carpeta nueva." }
    $requirements = if ($Telegram) { "requirements-telegram.txt" } else { "requirements-dev.txt" }
    & $envPython -m pip --disable-pip-version-check install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Fallo la instalacion de dependencias; revisa la salida de pip." }
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
