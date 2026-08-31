<#
.SYNOPSIS
Descarga desde Railway las ejecuciones Top-Down que no existen localmente.

.DESCRIPTION
Compara las carpetas de /app/Stories/Top-Down del servicio Railway enlazado
con Stories/Top-Down del repositorio. Archiva cada ejecución terminal, valida
su manifiesto y elimina la copia remota solamente después de comprobar la
integridad local.

.PARAMETER Concurrency
Cantidad máxima de archivos que Railway descarga simultáneamente. El valor
predeterminado es 8.

.PARAMETER KeepRemote
Conserva las carpetas remotas después de descargarlas y validarlas.

.EXAMPLE
.\sync-railway-stories.ps1

.EXAMPLE
.\sync-railway-stories.ps1 -Concurrency 16

.EXAMPLE
.\sync-railway-stories.ps1 -KeepRemote

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
    [int]$Concurrency = 8,

    [switch]$KeepRemote
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$remoteRoot = "/app/Stories/Top-Down"
$localRoot = Join-Path $PSScriptRoot "Stories\Top-Down"
$stagingRoot = Join-Path $PSScriptRoot "Stories\.railway-sync"

# Return the first matching property value from a flexible CLI object.
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

# Normalize supported Railway JSON wrappers into an entry collection.
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

# Extract and normalize the final path segment for a remote entry.
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

# Determine whether a Railway file entry represents a directory.
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

# Reject remote directory names that could escape the local target.
function Assert-SafeDirectoryName {
    param([Parameter(Mandatory = $true)][string]$Name)

    if ($Name -in @(".", "..", "telegram_queue.sqlite3") -or
        $Name.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
        $Name.Contains("/") -or $Name.Contains("\")) {
        throw "Railway devolvió un nombre de carpeta no seguro: '$Name'."
    }
}

# Validate a complete local archive before allowing removal of its remote copy.
function Test-ArchivedRun {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ExpectedRunId
    )

    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
            throw "No existe el directorio local esperado."
        }
        $reparsePoint = Get-ChildItem -LiteralPath $Path -Recurse -Force |
            Where-Object {
                ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
            } |
            Select-Object -First 1
        if ($null -ne $reparsePoint) {
            throw "El archivo '$($reparsePoint.FullName)' es un enlace o reparse point."
        }

        $metadataPath = Join-Path $Path "metadata.json"
        $manifestPath = Join-Path $Path "pipeline_manifest.json"
        if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
            throw "Falta metadata.json."
        }
        if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
            throw "Falta pipeline_manifest.json."
        }

        $metadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json
        $runId = Get-PropertyValue -InputObject $metadata -Names @("run_id")
        if ([string]$runId -cne $ExpectedRunId) {
            throw "metadata.json declara run_id '$runId', no '$ExpectedRunId'."
        }
        $status = [string](Get-PropertyValue -InputObject $metadata -Names @("status"))
        if ($status -eq "running") {
            return [pscustomobject]@{
                State = "pending"
                Message = "La ejecución todavía está activa."
            }
        }
        if ($status -notin @("completed", "failed")) {
            throw "El estado '$status' no es terminal."
        }

        $requiredArtifact = if ($status -eq "completed") { "story.md" } else { "error_report.json" }
        if (-not (Test-Path -LiteralPath (Join-Path $Path $requiredArtifact) -PathType Leaf)) {
            throw "La ejecución '$status' no contiene $requiredArtifact."
        }

        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
        $manifestRunId = Get-PropertyValue -InputObject $manifest -Names @("run_id")
        if ([string]$manifestRunId -cne $ExpectedRunId) {
            throw "pipeline_manifest.json declara run_id '$manifestRunId', no '$ExpectedRunId'."
        }
        $artifacts = Get-PropertyValue -InputObject $manifest -Names @("artifacts")
        if ($null -eq $artifacts -or @($artifacts.PSObject.Properties).Count -eq 0) {
            throw "El manifiesto no declara artefactos."
        }

        $archiveRoot = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
        foreach ($artifact in $artifacts.PSObject.Properties) {
            $relative = ([string]$artifact.Name).Replace('\', '/')
            $segments = @($relative -split '/')
            if ([System.IO.Path]::IsPathRooted($relative) -or
                $segments -contains '..' -or $segments -contains '.' -or
                [string]::IsNullOrWhiteSpace($relative)) {
                throw "El manifiesto contiene una ruta insegura: '$relative'."
            }
            $artifactPath = [System.IO.Path]::GetFullPath(
                (Join-Path $archiveRoot ($relative.Replace('/', '\')))
            )
            if (-not $artifactPath.StartsWith(
                $archiveRoot + [System.IO.Path]::DirectorySeparatorChar,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                throw "El artefacto '$relative' escapa de la carpeta archivada."
            }
            if (-not (Test-Path -LiteralPath $artifactPath -PathType Leaf)) {
                throw "Falta el artefacto '$relative'."
            }
            $expectedHash = Get-PropertyValue -InputObject $artifact.Value -Names @('sha256')
            if ([string]::IsNullOrWhiteSpace([string]$expectedHash)) {
                throw "El artefacto '$relative' no tiene SHA-256."
            }
            $actualHash = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash
            if ($actualHash -cne ([string]$expectedHash).ToUpperInvariant()) {
                throw "El SHA-256 de '$relative' no coincide con el manifiesto."
            }
        }

        return [pscustomobject]@{
            State = 'valid'
            Message = 'Archivo local íntegro.'
        }
    }
    catch {
        return [pscustomobject]@{
            State = 'invalid'
            Message = $_.Exception.Message
        }
    }
}

function Remove-RemoteRun {
    param([Parameter(Mandatory = $true)][string]$RemotePath)

    & railway service files delete $RemotePath --yes --json | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Railway CLI terminó con código $LASTEXITCODE al borrar."
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
    $existingLocal = 0
    $deleted = 0
    $pending = 0
    $integrityFailures = 0
    $downloadFailures = 0
    $deleteFailures = 0

    foreach ($name in $remoteNames) {
        $destination = Join-Path $localRoot $name
        $remotePath = "$remoteRoot/$name"
        $archiveReady = $false

        if (Test-Path -LiteralPath $destination) {
            $existingLocal++
            $validation = Test-ArchivedRun -Path $destination -ExpectedRunId $name
            if ($validation.State -eq "pending") {
                Write-Host "[pendiente] $($name): $($validation.Message)"
                $pending++
                continue
            }
            if ($validation.State -ne "valid") {
                Write-Warning "No se borrará '$name': $($validation.Message)"
                $integrityFailures++
                continue
            }
            Write-Host "[ya local] $name"
            $archiveReady = $true
        }
        else {
            $partialName = "$name.partial-$([Guid]::NewGuid().ToString('N'))"
            $partialPath = Join-Path $stagingRoot $partialName

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
            }
            catch {
                if (Test-Path -LiteralPath $partialPath) {
                    Remove-Item -LiteralPath $partialPath -Recurse -Force
                }
                Write-Warning "No se pudo descargar '$name': $($_.Exception.Message)"
                $downloadFailures++
                continue
            }

            $validation = Test-ArchivedRun -Path $partialPath -ExpectedRunId $name
            if ($validation.State -eq "pending") {
                Remove-Item -LiteralPath $partialPath -Recurse -Force
                Write-Host "[pendiente] $($name): $($validation.Message)"
                $pending++
                continue
            }
            if ($validation.State -ne "valid") {
                Remove-Item -LiteralPath $partialPath -Recurse -Force
                Write-Warning "La descarga de '$name' no pasó integridad: $($validation.Message)"
                $integrityFailures++
                continue
            }

            try {
                Move-Item -LiteralPath $partialPath -Destination $destination
            }
            catch {
                if (Test-Path -LiteralPath $partialPath) {
                    Remove-Item -LiteralPath $partialPath -Recurse -Force
                }
                Write-Warning "No se pudo archivar '$name': $($_.Exception.Message)"
                $downloadFailures++
                continue
            }
            Write-Host "[descargada] $name"
            $downloaded++
            $archiveReady = $true
        }

        if ($archiveReady -and -not $KeepRemote) {
            try {
                Remove-RemoteRun -RemotePath $remotePath
                Write-Host "[borrada] $name"
                $deleted++
            }
            catch {
                Write-Warning "La copia local de '$name' está íntegra, pero Railway no pudo borrarla: $($_.Exception.Message)"
                $deleteFailures++
            }
        }
        elseif ($archiveReady) {
            Write-Host "[conservada remota] $name"
        }
    }

    if ((Test-Path -LiteralPath $stagingRoot) -and
        $null -eq (Get-ChildItem -LiteralPath $stagingRoot -Force | Select-Object -First 1)) {
        Remove-Item -LiteralPath $stagingRoot -Force
    }

    Write-Host ""
    Write-Host (
        (
            "Sincronización terminada: {0} descargadas, {1} ya locales, {2} borradas, " +
            "{3} pendientes, {4} fallos de integridad, {5} fallos de descarga y " +
            "{6} fallos de borrado."
        ) -f
        $downloaded,
        $existingLocal,
        $deleted,
        $pending,
        $integrityFailures,
        $downloadFailures,
        $deleteFailures
    )

    if (($integrityFailures + $downloadFailures + $deleteFailures) -gt 0) {
        exit 1
    }
    exit 0
}
catch {
    Write-Error $_.Exception.Message
    exit 1
}
