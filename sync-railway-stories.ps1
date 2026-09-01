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

.PARAMETER DownloadRetryAttempts
Cantidad máxima de intentos para reparar cada artefacto que Railway no pudo
descargar correctamente. El valor predeterminado es 3.

.PARAMETER RetryDelaySeconds
Espera entre reintentos de un artefacto. El valor predeterminado es 2 segundos.

.EXAMPLE
.\sync-railway-stories.ps1

.EXAMPLE
.\sync-railway-stories.ps1 -Concurrency 16

.EXAMPLE
.\sync-railway-stories.ps1 -KeepRemote

.EXAMPLE
.\sync-railway-stories.ps1 -DownloadRetryAttempts 5 -RetryDelaySeconds 1

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

    [switch]$KeepRemote,

    [ValidateRange(1, 10)]
    [int]$DownloadRetryAttempts = 3,

    [ValidateRange(0, 60)]
    [int]$RetryDelaySeconds = 2
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

function Invoke-RailwayDownload {
    param(
        [string]$RemotePath,
        [string]$LocalPath,
        [int]$TransferConcurrency = 0,
        [switch]$Overwrite
    )
    $arguments = @("service", "files", "download", $RemotePath, $LocalPath, "--json")
    if ($Overwrite) { $arguments += "--overwrite" }
    if ($TransferConcurrency -gt 0) {
        $arguments += @("--concurrency", [string]$TransferConcurrency)
    }
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& railway @arguments 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $oldPreference }
    [pscustomobject]@{
        Succeeded = ($exitCode -eq 0)
        ExitCode = $exitCode
        Message = (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
    }
}

function Get-SafeArtifactDescriptor {
    param(
        [string]$ArchivePath,
        $Artifact
    )
    $relative = ([string]$Artifact.Name).Replace('\', '/')
    $segments = @($relative -split '/')
    if ([System.IO.Path]::IsPathRooted($relative) -or
        $segments -contains '..' -or $segments -contains '.' -or
        [string]::IsNullOrWhiteSpace($relative)) {
        throw "El manifiesto contiene una ruta insegura: '$relative'."
    }
    $archiveRoot = [System.IO.Path]::GetFullPath($ArchivePath).TrimEnd('\', '/')
    $artifactPath = [System.IO.Path]::GetFullPath(
        (Join-Path $archiveRoot ($relative.Replace('/', '\')))
    )
    if (-not $artifactPath.StartsWith(
        $archiveRoot + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "El artefacto '$relative' escapa de la carpeta archivada."
    }
    $expectedHash = Get-PropertyValue -InputObject $Artifact.Value -Names @('sha256')
    if ([string]::IsNullOrWhiteSpace([string]$expectedHash)) {
        throw "El artefacto '$relative' no tiene SHA-256."
    }
    [pscustomobject]@{
        RelativePath = $relative
        LocalPath = $artifactPath
        ExpectedHash = ([string]$expectedHash).ToUpperInvariant()
    }
}

function Repair-PartialRun {
    param(
        [string]$PartialPath,
        [string]$RemotePath,
        [string]$ExpectedRunId,
        [int]$Attempts,
        [int]$DelaySeconds
    )
    try {
        New-Item -ItemType Directory -Path $PartialPath -Force | Out-Null
        foreach ($controlFile in @("metadata.json", "pipeline_manifest.json")) {
            $localControlPath = Join-Path $PartialPath $controlFile
            $controlReady = $false
            for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
                Write-Host "[reparando $attempt/$Attempts] $ExpectedRunId/$controlFile"
                $result = Invoke-RailwayDownload `
                    -RemotePath "$RemotePath/$controlFile" `
                    -LocalPath $localControlPath `
                    -Overwrite
                if ($result.Succeeded -and
                    (Test-Path -LiteralPath $localControlPath -PathType Leaf)) {
                    $controlReady = $true
                    break
                }
                if ($attempt -lt $Attempts -and $DelaySeconds -gt 0) {
                    Start-Sleep -Seconds $DelaySeconds
                }
            }
            if (-not $controlReady) {
                throw "No se pudo recuperar $controlFile. $($result.Message)"
            }
        }

        $metadata = Get-Content -LiteralPath (Join-Path $PartialPath "metadata.json") -Raw |
            ConvertFrom-Json
        $metadataRunId = Get-PropertyValue -InputObject $metadata -Names @("run_id")
        if ([string]$metadataRunId -cne $ExpectedRunId) {
            throw "metadata.json declara run_id '$metadataRunId', no '$ExpectedRunId'."
        }
        $manifest = Get-Content -LiteralPath (Join-Path $PartialPath "pipeline_manifest.json") -Raw |
            ConvertFrom-Json
        $manifestRunId = Get-PropertyValue -InputObject $manifest -Names @("run_id")
        if ([string]$manifestRunId -cne $ExpectedRunId) {
            throw "pipeline_manifest.json declara run_id '$manifestRunId', no '$ExpectedRunId'."
        }
        $artifacts = Get-PropertyValue -InputObject $manifest -Names @("artifacts")
        if ($null -eq $artifacts -or @($artifacts.PSObject.Properties).Count -eq 0) {
            throw "El manifiesto no declara artefactos."
        }

        $repairTargets = @(
            foreach ($artifact in $artifacts.PSObject.Properties) {
                $descriptor = Get-SafeArtifactDescriptor `
                    -ArchivePath $PartialPath `
                    -Artifact $artifact
                $needsRepair = -not (Test-Path -LiteralPath $descriptor.LocalPath -PathType Leaf)
                if (-not $needsRepair) {
                    $actualHash = (Get-FileHash -LiteralPath $descriptor.LocalPath -Algorithm SHA256).Hash
                    $needsRepair = $actualHash -cne $descriptor.ExpectedHash
                }
                if ($needsRepair) { $descriptor }
            }
        )
        if ($repairTargets.Count -gt 0) {
            Write-Host "[reparación] $($ExpectedRunId): $($repairTargets.Count) artefacto(s) incompleto(s)."
        }
        foreach ($target in $repairTargets) {
            New-Item -ItemType Directory -Path (Split-Path -Parent $target.LocalPath) -Force |
                Out-Null
            $repaired = $false
            for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
                Write-Host "[reparando $attempt/$Attempts] $ExpectedRunId/$($target.RelativePath)"
                $result = Invoke-RailwayDownload `
                    -RemotePath "$RemotePath/$($target.RelativePath)" `
                    -LocalPath $target.LocalPath `
                    -Overwrite
                if ($result.Succeeded -and
                    (Test-Path -LiteralPath $target.LocalPath -PathType Leaf)) {
                    $actualHash = (Get-FileHash -LiteralPath $target.LocalPath -Algorithm SHA256).Hash
                    if ($actualHash -ceq $target.ExpectedHash) {
                        $repaired = $true
                        break
                    }
                }
                if ($attempt -lt $Attempts -and $DelaySeconds -gt 0) {
                    Start-Sleep -Seconds $DelaySeconds
                }
            }
            if (-not $repaired) {
                throw "No se pudo reparar '$($target.RelativePath)'. $($result.Message)"
            }
        }
        [pscustomobject]@{ Succeeded = $true; Message = "Descarga parcial reparada." }
    }
    catch {
        [pscustomobject]@{ Succeeded = $false; Message = $_.Exception.Message }
    }
}

function New-ManualDeleteCommand {
    param(
        [string]$RemotePath,
        [string]$ServiceName
    )
    $escapedServiceName = $ServiceName.Replace("'", "''")
    $escapedRemotePath = $RemotePath.Replace("'", "''")
    "railway service '$escapedServiceName' files delete '$escapedRemotePath' --yes"
}

function Invoke-RemoteRunDeletion {
    param(
        [string]$RemotePath,
        [string]$ServiceName
    )
    $oldPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $output = @(& railway service files delete $RemotePath --yes --json 2>&1)
        $exitCode = $LASTEXITCODE
    }
    finally { $ErrorActionPreference = $oldPreference }

    $message = (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
    $manualCommand = New-ManualDeleteCommand `
        -RemotePath $RemotePath `
        -ServiceName $ServiceName
    if ($exitCode -eq 0) {
        return [pscustomobject]@{ State = "deleted"; Message = $message; Command = $null }
    }
    if ($message -match "agents cannot delete files") {
        return [pscustomobject]@{
            State = "agent-blocked"
            Message = $message
            Command = $manualCommand
        }
    }
    [pscustomobject]@{
        State = "failed"
        Message = "Railway CLI terminó con código $exitCode al borrar. $message"
        Command = $manualCommand
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
    $serviceData = Get-PropertyValue -InputObject $jsonData -Names @("service")
    $remoteServiceName = if ($null -ne $serviceData) {
        [string](Get-PropertyValue -InputObject $serviceData -Names @("name"))
    }
    else { "" }
    if ([string]::IsNullOrWhiteSpace($remoteServiceName)) {
        $remoteServiceName = "biplan-telegram"
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
    $manualDeletes = 0
    $remoteDeletionBlocked = $false
    $manualDeleteCommands = New-Object System.Collections.Generic.List[string]

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

            Write-Host "[descargando] $name"
            $bulkResult = Invoke-RailwayDownload `
                -RemotePath $remotePath `
                -LocalPath $partialPath `
                -TransferConcurrency $Concurrency
            if (-not $bulkResult.Succeeded) {
                Write-Warning (
                    "La descarga completa de '$name' falló; se repararán solamente " +
                    "los artefactos incompletos. $($bulkResult.Message)"
                )
                $repair = Repair-PartialRun `
                    -PartialPath $partialPath `
                    -RemotePath $remotePath `
                    -ExpectedRunId $name `
                    -Attempts $DownloadRetryAttempts `
                    -DelaySeconds $RetryDelaySeconds
                if (-not $repair.Succeeded) {
                    if (Test-Path -LiteralPath $partialPath) {
                        Remove-Item -LiteralPath $partialPath -Recurse -Force
                    }
                    Write-Warning "No se pudo descargar '$name': $($repair.Message)"
                    $downloadFailures++
                    continue
                }
            }
            if (-not (Test-Path -LiteralPath $partialPath -PathType Container)) {
                Write-Warning "No se pudo descargar '$name': Railway no creó el directorio esperado."
                $downloadFailures++
                continue
            }
            if (Test-Path -LiteralPath $destination) {
                Remove-Item -LiteralPath $partialPath -Recurse -Force
                Write-Warning "La carpeta local '$name' apareció durante la descarga; no se sobrescribirá."
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
            if ($remoteDeletionBlocked) {
                $manualDeleteCommands.Add(
                    (New-ManualDeleteCommand `
                        -RemotePath $remotePath `
                        -ServiceName $remoteServiceName)
                )
                $manualDeletes++
                Write-Host "[borrado manual pendiente] $name"
            }
            else {
                $deleteResult = Invoke-RemoteRunDeletion `
                    -RemotePath $remotePath `
                    -ServiceName $remoteServiceName
                if ($deleteResult.State -eq "deleted") {
                    Write-Host "[borrada] $name"
                    $deleted++
                }
                elseif ($deleteResult.State -eq "agent-blocked") {
                    $remoteDeletionBlocked = $true
                    $manualDeleteCommands.Add($deleteResult.Command)
                    $manualDeletes++
                    Write-Warning (
                        "Railway bloqueó el borrado desde esta terminal marcada como agente. " +
                        "Las descargas continuarán y los comandos manuales se mostrarán al final."
                    )
                    Write-Host "[borrado manual pendiente] $name"
                }
                else {
                    Write-Warning "Railway no pudo borrar '$name': $($deleteResult.Message)"
                    $deleteFailures++
                }
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

    if ($manualDeleteCommands.Count -gt 0) {
        Write-Host ""
        Write-Warning (
            "Hay $manualDeletes copia(s) remota(s) validadas cuyo borrado requiere " +
            "un PowerShell externo no marcado como agente. Ejecuta:"
        )
        foreach ($command in $manualDeleteCommands) {
            Write-Host "  $command"
        }
    }

    Write-Host ""
    Write-Host (
        (
            "Sincronización terminada: {0} descargadas, {1} ya locales, {2} borradas, " +
            "{3} pendientes, {4} fallos de integridad, {5} fallos de descarga y " +
            "{6} fallos de borrado; {7} borrados manuales pendientes."
        ) -f
        $downloaded,
        $existingLocal,
        $deleted,
        $pending,
        $integrityFailures,
        $downloadFailures,
        $deleteFailures,
        $manualDeletes
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
