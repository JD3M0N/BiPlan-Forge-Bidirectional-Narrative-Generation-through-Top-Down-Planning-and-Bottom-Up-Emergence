<#
.SYNOPSIS
Descarga desde Railway las ejecuciones Top-Down que no existen localmente.

.DESCRIPTION
Compara las carpetas de /app/Stories/Top-Down del servicio Railway enlazado
con Stories/Top-Down del repositorio. Descarga solamente las carpetas ausentes,
sin sobrescribir contenido local ni modificar archivos remotos.

.PARAMETER Concurrency
Cantidad máxima de archivos que Railway descarga simultáneamente. El valor
predeterminado es 8.

.EXAMPLE
.\sync-railway-stories.ps1

.EXAMPLE
.\sync-railway-stories.ps1 -Concurrency 16

.NOTES
Preparación inicial:
  npm install -g @railway/cli
  railway login
  railway link

Al enlazar el repositorio, selecciona el servicio biplan-telegram.
#>

[CmdletBinding()]
param(
    [ValidateRange(1, 128)]
    [int]$Concurrency = 8
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$remoteRoot = "/app/Stories/Top-Down"
$localRoot = Join-Path $PSScriptRoot "Stories\Top-Down"
$stagingRoot = Join-Path $PSScriptRoot "Stories\.railway-sync"

function Get-PropertyValue {
    param(
        [Parameter(Mandatory = $true)]$InputObject,
        [Parameter(Mandatory = $true)][string[]]$Names
    )

    foreach ($property in $InputObject.PSObject.Properties) {
        if ($Names -contains $property.Name) {
            return $property.Value
        }
    }
    return $null
}

function Get-EntryCollection {
    param([Parameter(Mandatory = $true)]$JsonData)

    if ($JsonData -is [System.Array]) {
        return @($JsonData)
    }

    $wrapped = Get-PropertyValue -InputObject $JsonData -Names @(
        "entries", "files", "items", "data"
    )
    if ($null -ne $wrapped) {
        return @($wrapped)
    }
    return @($JsonData)
}

function Get-EntryName {
    param([Parameter(Mandatory = $true)]$Entry)

    if ($Entry -is [string]) {
        $rawName = $Entry
    }
    else {
        $rawName = Get-PropertyValue -InputObject $Entry -Names @(
            "name", "path", "remotePath", "key"
        )
    }
    if ([string]::IsNullOrWhiteSpace([string]$rawName)) {
        return $null
    }

    $normalized = ([string]$rawName).Replace("\", "/").TrimEnd("/")
    return ($normalized -split "/")[-1]
}

function Test-DirectoryEntry {
    param([Parameter(Mandatory = $true)]$Entry)

    if ($Entry -is [string]) {
        return $true
    }

    $directoryFlag = Get-PropertyValue -InputObject $Entry -Names @(
        "isDirectory", "isDir", "is_directory", "directory"
    )
    if ($null -ne $directoryFlag) {
        return [bool]$directoryFlag
    }

    $entryType = Get-PropertyValue -InputObject $Entry -Names @(
        "type", "kind", "fileType"
    )
    if ($null -ne $entryType) {
        return ([string]$entryType).ToLowerInvariant() -in @(
            "directory", "dir", "folder"
        )
    }

    # Las versiones antiguas del CLI no siempre incluyeron el tipo en JSON.
    # El directorio remoto contiene solamente carpetas de ejecuciones.
    return $true
}

function Assert-SafeDirectoryName {
    param([Parameter(Mandatory = $true)][string]$Name)

    if ($Name -in @(".", "..", "telegram_queue.sqlite3") -or
        $Name.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
        $Name.Contains("/") -or $Name.Contains("\")) {
        throw "Railway devolvió un nombre de carpeta no seguro: '$Name'."
    }
}

if ($null -eq (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Error (
        "No se encontró Railway CLI. Instálalo con: " +
        "npm install -g @railway/cli"
    )
    exit 1
}

& railway whoami *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Railway CLI no está autenticado. Ejecuta: railway login"
    exit 1
}

& railway status --json *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error (
        "Este repositorio no está enlazado con Railway. Ejecuta: railway link " +
        "y selecciona el servicio biplan-telegram."
    )
    exit 1
}

try {
    $jsonLines = @(& railway service files list $remoteRoot --json)
    if ($LASTEXITCODE -ne 0) {
        throw (
            "No se pudo listar $remoteRoot. Confirma que railway link apunta " +
            "al servicio biplan-telegram y que el deployment está activo."
        )
    }

    $jsonText = $jsonLines -join [Environment]::NewLine
    try {
        $jsonData = $jsonText | ConvertFrom-Json
    }
    catch {
        throw "Railway devolvió una lista JSON inválida: $($_.Exception.Message)"
    }

    $remoteNames = @(
        foreach ($entry in (Get-EntryCollection -JsonData $jsonData)) {
            if (-not (Test-DirectoryEntry -Entry $entry)) {
                continue
            }
            $name = Get-EntryName -Entry $entry
            if ([string]::IsNullOrWhiteSpace($name)) {
                continue
            }
            Assert-SafeDirectoryName -Name $name
            $name
        }
    ) | Sort-Object -Unique

    New-Item -ItemType Directory -Path $localRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

    $downloaded = 0
    $skipped = 0
    $failed = 0

    foreach ($name in $remoteNames) {
        $destination = Join-Path $localRoot $name
        if (Test-Path -LiteralPath $destination) {
            Write-Host "[omitida] $name"
            $skipped++
            continue
        }

        $partialName = "$name.partial-$([Guid]::NewGuid().ToString('N'))"
        $partialPath = Join-Path $stagingRoot $partialName
        $remotePath = "$remoteRoot/$name"

        try {
            Write-Host "[descargando] $name"
            & railway service files download $remotePath $partialPath `
                --concurrency $Concurrency --json | Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "Railway CLI terminó con código $LASTEXITCODE."
            }
            if (-not (Test-Path -LiteralPath $partialPath -PathType Container)) {
                throw "Railway no creó el directorio local esperado."
            }
            if (Test-Path -LiteralPath $destination) {
                throw "La carpeta local apareció durante la descarga; no se sobrescribirá."
            }

            Move-Item -LiteralPath $partialPath -Destination $destination
            Write-Host "[descargada] $name"
            $downloaded++
        }
        catch {
            if (Test-Path -LiteralPath $partialPath) {
                Remove-Item -LiteralPath $partialPath -Recurse -Force
            }
            Write-Warning "No se pudo descargar '$name': $($_.Exception.Message)"
            $failed++
        }
    }

    if ((Test-Path -LiteralPath $stagingRoot) -and
        $null -eq (Get-ChildItem -LiteralPath $stagingRoot -Force | Select-Object -First 1)) {
        Remove-Item -LiteralPath $stagingRoot -Force
    }

    Write-Host ""
    Write-Host (
        "Sincronización terminada: {0} descargadas, {1} omitidas, {2} fallidas." -f
        $downloaded, $skipped, $failed
    )

    if ($failed -gt 0) {
        exit 1
    }
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
