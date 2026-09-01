$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceScript = Join-Path $repoRoot "sync-railway-stories.ps1"
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "asg-railway-sync-test-" + [Guid]::NewGuid().ToString("N")
)
$powershellExe = (Get-Command powershell.exe).Source
$originalPath = $env:PATH

# Fail the script when a test condition is false.
function Assert-True {
    param([bool]$Condition, [string]$Message)
    if (-not $Condition) {
        throw $Message
    }
}

$sourceBytes = [System.IO.File]::ReadAllBytes($sourceScript)
Assert-True (
    $sourceBytes.Length -ge 3 -and
    $sourceBytes[0] -eq 0xEF -and $sourceBytes[1] -eq 0xBB -and $sourceBytes[2] -eq 0xBF
) "El sincronizador no está guardado con BOM UTF-8 para PowerShell 5.1."

# Create one fake run whose manifest hashes match its on-disk artifacts.
function New-TestRun {
    param(
        [string]$Root,
        [string]$Name,
        [string]$Status = "completed",
        [switch]$CorruptHash,
        [switch]$OmitManifest,
        [switch]$WithAudio
    )

    $run = Join-Path $Root $Name
    New-Item -ItemType Directory -Path $run -Force | Out-Null
    $metadataPath = Join-Path $run "metadata.json"
    [pscustomobject]@{ run_id = $Name; status = $Status; pipeline_version = "5.2" } |
        ConvertTo-Json |
        Set-Content -LiteralPath $metadataPath -Encoding UTF8
    if ($Status -eq "completed") {
        Set-Content -LiteralPath (Join-Path $run "story.md") -Value "story for $Name" -Encoding UTF8
    }
    elseif ($Status -eq "failed") {
        Set-Content -LiteralPath (Join-Path $run "error_report.json") -Value "{}" -Encoding UTF8
    }
    if ($WithAudio) {
        [System.IO.File]::WriteAllBytes((Join-Path $run "story.mp3"), ([byte[]](1..255)))
    }
    if (-not $OmitManifest) {
        $artifacts = [ordered]@{}
        foreach ($file in (Get-ChildItem -LiteralPath $run -File)) {
            $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($CorruptHash -and $file.Name -eq "story.md") {
                $hash = "0" * 64
            }
            $artifacts[$file.Name] = [ordered]@{ sha256 = $hash; bytes = $file.Length }
        }
        [ordered]@{ run_id = $Name; artifacts = $artifacts } |
            ConvertTo-Json -Depth 5 |
            Set-Content -LiteralPath (Join-Path $run "pipeline_manifest.json") -Encoding UTF8
    }
    return $run
}

# Run the sync script and return its expected nonzero exit code.
function Invoke-SyncExpectFailure {
    param([string]$PowerShellPath, [string]$ScriptPath)

    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath `
            1>$null 2>$null
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

try {
    $fakeBin = Join-Path $testRoot "fake-bin"
    $fakeRemote = Join-Path $testRoot "remote"
    $testRepo = Join-Path $testRoot "repo"
    New-Item -ItemType Directory -Path $fakeBin, $fakeRemote, $testRepo -Force | Out-Null
    Copy-Item -LiteralPath $sourceScript -Destination $testRepo

    $fakeRailway = @'
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs)

$mode = $env:FAKE_RAILWAY_MODE
$command = $CliArgs -join " "

if ($CliArgs[0] -eq "whoami") {
    if ($mode -eq "unauthenticated") { exit 1 }
    Write-Output "test-user"
    exit 0
}
if ($CliArgs[0] -eq "status") {
    if ($mode -eq "unlinked") { exit 1 }
    Write-Output '{"service":"biplan-telegram"}'
    exit 0
}
if ($command -match '^service files list ') {
    if ($mode -eq "invalid-json") {
        Write-Output "not-json"
        exit 0
    }
    $entries = @(
        Get-ChildItem -LiteralPath $env:FAKE_RAILWAY_SOURCE -Directory |
            ForEach-Object { [pscustomobject]@{ name = $_.Name; type = "directory" } }
    )
    [pscustomobject]@{
        entries = @($entries) + @([pscustomobject]@{ name = "ignored.txt"; type = "file" })
    } | ConvertTo-Json -Depth 4 -Compress
    exit 0
}
if ($command -match '^service files download ') {
    $remotePath = $CliArgs[3]
    $localPath = $CliArgs[4]
    $parts = @(($remotePath.Replace("\", "/").Trim("/")) -split "/")
    $rootIndex = [Array]::IndexOf($parts, "Top-Down")
    $name = $parts[$rootIndex + 1]
    $relativeParts = @($parts | Select-Object -Skip ($rootIndex + 2))
    if ($relativeParts.Count -eq 0) {
        Add-Content -LiteralPath $env:FAKE_RAILWAY_LOG -Value $name
        New-Item -ItemType Directory -Path $localPath -Force | Out-Null
        Copy-Item -Path (Join-Path (Join-Path $env:FAKE_RAILWAY_SOURCE $name) "*") `
            -Destination $localPath -Recurse -Force
        if ($name -eq $env:FAKE_RAILWAY_FAIL_NAME -or
            $name -eq $env:FAKE_RAILWAY_BULK_TIMEOUT_NAME) {
            $corruptPath = Join-Path $localPath "story.mp3"
            if (-not (Test-Path -LiteralPath $corruptPath)) {
                $corruptPath = Join-Path $localPath "story.md"
            }
            Set-Content -LiteralPath $corruptPath -Value "partial" -Encoding UTF8
            exit 9
        }
    }
    else {
        $relative = $relativeParts -join "/"
        Add-Content -LiteralPath $env:FAKE_RAILWAY_REPAIR_LOG -Value "$name/$relative"
        $parent = Split-Path -Parent $localPath
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        if ($name -eq $env:FAKE_RAILWAY_FAIL_NAME -or
            "$name/$relative" -eq $env:FAKE_RAILWAY_ARTIFACT_FAIL) {
            exit 9
        }
        Copy-Item -LiteralPath (Join-Path (Join-Path $env:FAKE_RAILWAY_SOURCE $name) $relative) `
            -Destination $localPath -Force
    }
    Write-Output '{"ok":true}'
    exit 0
}
if ($command -match '^service files delete ') {
    $remotePath = $CliArgs[3]
    $name = ($remotePath.Replace('\', '/') -split '/')[-1]
    Add-Content -LiteralPath $env:FAKE_RAILWAY_DELETE_LOG -Value $name
    if ($env:FAKE_RAILWAY_AGENT_DELETE -eq "1") {
        Write-Output "Refusing: agents cannot delete files. Ask a human to run:"
        exit 1
    }
    if ($name -eq $env:FAKE_RAILWAY_DELETE_FAIL_NAME) { exit 7 }
    Remove-Item -LiteralPath (Join-Path $env:FAKE_RAILWAY_SOURCE $name) -Recurse -Force
    Write-Output '{"ok":true}'
    exit 0
}
exit 2
'@
    Set-Content -LiteralPath (Join-Path $fakeBin "railway.ps1") `
        -Value $fakeRailway -Encoding UTF8

    $localRuns = Join-Path $testRepo "Stories\Top-Down"
    New-Item -ItemType Directory -Path $localRuns -Force | Out-Null
    $existing = New-TestRun -Root $localRuns -Name "existing-run"
    $existingRemote = New-TestRun -Root $fakeRemote -Name "existing-run"
    $newRemote = New-TestRun -Root $fakeRemote -Name "new-run"
    Set-Content -LiteralPath (Join-Path $existing "local-marker.txt") -Value "local"

    $env:PATH = "$fakeBin;$originalPath"
    $env:FAKE_RAILWAY_SOURCE = $fakeRemote
    $env:FAKE_RAILWAY_LOG = Join-Path $testRoot "downloads.log"
    $env:FAKE_RAILWAY_REPAIR_LOG = Join-Path $testRoot "repairs.log"
    $env:FAKE_RAILWAY_DELETE_LOG = Join-Path $testRoot "deletes.log"
    $env:FAKE_RAILWAY_MODE = ""
    $env:FAKE_RAILWAY_FAIL_NAME = ""
    $env:FAKE_RAILWAY_BULK_TIMEOUT_NAME = ""
    $env:FAKE_RAILWAY_ARTIFACT_FAIL = ""
    $env:FAKE_RAILWAY_AGENT_DELETE = ""
    $env:FAKE_RAILWAY_DELETE_FAIL_NAME = ""

    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 0) "La sincronización inicial falló."
    Assert-True (Test-Path (Join-Path $testRepo "Stories\Top-Down\new-run\story.md")) `
        "No se descargó la ejecución nueva."
    Assert-True ((Get-Content (Join-Path $existing "local-marker.txt")) -eq "local") `
        "Se modificó una ejecución local existente."
    Assert-True (-not (Test-Path $existingRemote)) "No se borró la ejecución remota ya archivada."
    Assert-True (-not (Test-Path $newRemote)) "No se borró la ejecución recién descargada."
    Assert-True (@(Get-Content $env:FAKE_RAILWAY_DELETE_LOG).Count -eq 2) "No se registraron los dos borrados remotos esperados."
    Assert-True (-not (Test-Path (Join-Path $testRepo "Stories\.railway-sync"))) `
        "No se limpió el staging después del éxito."

    $secondOutput = @(
        & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (
            Join-Path $testRepo "sync-railway-stories.ps1"
        )
    )
    Assert-True ($LASTEXITCODE -eq 0) "La segunda sincronización falló."
    Assert-True (@(Get-Content $env:FAKE_RAILWAY_LOG).Count -eq 1) "Se volvió a descargar una ejecución existente."
    Assert-True (($secondOutput -join [Environment]::NewLine) -match "0 descargadas, 0 ya locales, 0 borradas") "El resumen no sustituyó correctamente sus contadores."

    $retryRemote = New-TestRun -Root $fakeRemote -Name "retry-audio-run" -WithAudio
    $expectedAudioHash = (Get-FileHash -LiteralPath (Join-Path $retryRemote "story.mp3") `
        -Algorithm SHA256).Hash
    $env:FAKE_RAILWAY_BULK_TIMEOUT_NAME = "retry-audio-run"
    & $powershellExe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $testRepo "sync-railway-stories.ps1") `
        -DownloadRetryAttempts 2 -RetryDelaySeconds 0
    Assert-True ($LASTEXITCODE -eq 0) "La reparación de un audio con timeout falló."
    $repairedAudio = Join-Path $localRuns "retry-audio-run\story.mp3"
    Assert-True (Test-Path -LiteralPath $repairedAudio -PathType Leaf) `
        "La reparación no archivó story.mp3."
    Assert-True ((Get-FileHash -LiteralPath $repairedAudio -Algorithm SHA256).Hash -ceq `
        $expectedAudioHash) "El audio reparado no coincide con el manifiesto."
    Assert-True ((Get-Content $env:FAKE_RAILWAY_REPAIR_LOG) -contains `
        "retry-audio-run/story.mp3") "No se reintentó individualmente story.mp3."
    Assert-True (-not (Test-Path $retryRemote)) `
        "No se borró el remoto después de reparar y validar el audio."

    $persistentRemote = New-TestRun -Root $fakeRemote -Name "persistent-timeout-run" -WithAudio
    $env:FAKE_RAILWAY_BULK_TIMEOUT_NAME = "persistent-timeout-run"
    $env:FAKE_RAILWAY_ARTIFACT_FAIL = "persistent-timeout-run/story.mp3"
    & $powershellExe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $testRepo "sync-railway-stories.ps1") `
        -DownloadRetryAttempts 2 -RetryDelaySeconds 0
    Assert-True ($LASTEXITCODE -eq 1) "Un timeout persistente no devolvió código 1."
    Assert-True (-not (Test-Path (Join-Path $localRuns "persistent-timeout-run"))) `
        "Un timeout persistente dejó una carpeta local definitiva."
    Assert-True (Test-Path $persistentRemote) `
        "Un timeout persistente borró la única copia remota."
    Assert-True (-not (Test-Path (Join-Path $testRepo "Stories\.railway-sync"))) `
        "Un timeout persistente dejó staging residual."
    Remove-Item -LiteralPath $persistentRemote -Recurse -Force
    $env:FAKE_RAILWAY_BULK_TIMEOUT_NAME = ""
    $env:FAKE_RAILWAY_ARTIFACT_FAIL = ""

    $deleteFailRemote = New-TestRun -Root $fakeRemote -Name "delete-fail-run"
    $env:FAKE_RAILWAY_DELETE_FAIL_NAME = "delete-fail-run"
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 1) "Un borrado fallido no devolvió código 1."
    Assert-True (Test-Path (Join-Path $localRuns "delete-fail-run\story.md")) "Se perdió la copia local tras fallar el borrado."
    Assert-True (Test-Path $deleteFailRemote) "Se eliminó la copia remota pese al fallo simulado."
    $downloadsBeforeRetry = @(Get-Content $env:FAKE_RAILWAY_LOG).Count
    $env:FAKE_RAILWAY_DELETE_FAIL_NAME = ""
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 0) "El reintento del borrado falló."
    Assert-True (@(Get-Content $env:FAKE_RAILWAY_LOG).Count -eq $downloadsBeforeRetry) "El reintento volvió a descargar la ejecución."
    Assert-True (-not (Test-Path $deleteFailRemote)) "El reintento no borró la copia remota."

    $agentRemoteOne = New-TestRun -Root $fakeRemote -Name "agent-cleanup-one"
    $agentRemoteTwo = New-TestRun -Root $fakeRemote -Name "agent-cleanup-two"
    $deleteAttemptsBeforeAgent = @(Get-Content $env:FAKE_RAILWAY_DELETE_LOG).Count
    $env:FAKE_RAILWAY_AGENT_DELETE = "1"
    $agentOutput = @(
        & $powershellExe -NoProfile -ExecutionPolicy Bypass `
            -File (Join-Path $testRepo "sync-railway-stories.ps1")
    )
    $agentText = $agentOutput -join [Environment]::NewLine
    Assert-True ($LASTEXITCODE -eq 0) `
        "El bloqueo de agente se trató como un fallo de sincronización."
    Assert-True ((@(Get-Content $env:FAKE_RAILWAY_DELETE_LOG).Count - `
        $deleteAttemptsBeforeAgent) -eq 1) `
        "Se siguieron intentando borrados después de detectar el bloqueo de agente."
    Assert-True ((Test-Path $agentRemoteOne) -and (Test-Path $agentRemoteTwo)) `
        "El doble eliminó remotos pese al bloqueo de agente."
    Assert-True ((Test-Path (Join-Path $localRuns "agent-cleanup-one\story.md")) -and `
        (Test-Path (Join-Path $localRuns "agent-cleanup-two\story.md"))) `
        "El bloqueo de borrado impidió completar las descargas locales."
    Assert-True ($agentText -match "2 borrados manuales pendientes") `
        "El resumen no contó los dos borrados manuales."
    Assert-True ($agentText -match "railway service 'biplan-telegram' files delete '.+' --yes") `
        "No se mostraron los comandos de borrado manual."
    Assert-True ($agentText -notmatch "files delete --service") `
        "Se mostró la sintaxis inválida --service para files delete."
    Assert-True ($agentText -match "Railway bloqueó" -and $agentText -notmatch "bloqueÃ") `
        "La salida UTF-8 se corrompió bajo Windows PowerShell 5.1."
    $env:FAKE_RAILWAY_AGENT_DELETE = ""
    Remove-Item -LiteralPath $agentRemoteOne, $agentRemoteTwo -Recurse -Force
    Remove-Item -LiteralPath `
        (Join-Path $localRuns "agent-cleanup-one"), `
        (Join-Path $localRuns "agent-cleanup-two") -Recurse -Force

    $failedRemote = New-TestRun -Root $fakeRemote -Name "failed-run"
    $env:FAKE_RAILWAY_FAIL_NAME = "failed-run"
    & $powershellExe -NoProfile -ExecutionPolicy Bypass `
        -File (Join-Path $testRepo "sync-railway-stories.ps1") `
        -DownloadRetryAttempts 2 -RetryDelaySeconds 0
    Assert-True ($LASTEXITCODE -eq 1) "Una descarga fallida no devolvió código 1."
    Assert-True (-not (Test-Path (Join-Path $localRuns "failed-run"))) "Una descarga fallida dejó una carpeta final incompleta."
    Assert-True (Test-Path $failedRemote) "Una descarga fallida borró la copia remota."
    Remove-Item -LiteralPath $failedRemote -Recurse -Force

    $env:FAKE_RAILWAY_FAIL_NAME = ""
    $corruptRemote = New-TestRun -Root $fakeRemote -Name "corrupt-run" -CorruptHash
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 1) "Un hash incorrecto no devolvió código 1."
    Assert-True (-not (Test-Path (Join-Path $localRuns "corrupt-run"))) "Se archivó una ejecución con hash incorrecto."
    Assert-True (Test-Path $corruptRemote) "Se borró una ejecución remota con hash incorrecto."
    Remove-Item -LiteralPath $corruptRemote -Recurse -Force

    $missingManifest = New-TestRun -Root $fakeRemote -Name "missing-manifest" -OmitManifest
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 1) "Un manifiesto ausente no devolvió código 1."
    Assert-True (-not (Test-Path (Join-Path $localRuns "missing-manifest"))) "Se archivó una ejecución sin manifiesto."
    Assert-True (Test-Path $missingManifest) "Se borró una ejecución remota sin manifiesto."
    Remove-Item -LiteralPath $missingManifest -Recurse -Force

    $runningRemote = New-TestRun -Root $fakeRemote -Name "running-run" -Status "running"
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 0) "Una ejecución activa produjo un fallo."
    Assert-True (-not (Test-Path (Join-Path $localRuns "running-run"))) "Se archivó una ejecución todavía activa."
    Assert-True (Test-Path $runningRemote) "Se borró una ejecución todavía activa."
    Remove-Item -LiteralPath $runningRemote -Recurse -Force

    $keptRemote = New-TestRun -Root $fakeRemote -Name "kept-run"
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $testRepo "sync-railway-stories.ps1") -KeepRemote
    Assert-True ($LASTEXITCODE -eq 0) "-KeepRemote produjo un fallo."
    Assert-True (Test-Path (Join-Path $localRuns "kept-run\story.md")) "-KeepRemote no descargó la ejecución."
    Assert-True (Test-Path $keptRemote) "-KeepRemote borró la ejecución remota."
    Remove-Item -LiteralPath $keptRemote -Recurse -Force

    $env:FAKE_RAILWAY_MODE = "invalid-json"
    $failureCode = Invoke-SyncExpectFailure -PowerShellPath $powershellExe `
        -ScriptPath (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($failureCode -eq 1) "El JSON inválido no devolvió código 1."

    $env:FAKE_RAILWAY_MODE = "unauthenticated"
    $failureCode = Invoke-SyncExpectFailure -PowerShellPath $powershellExe `
        -ScriptPath (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($failureCode -eq 1) "La falta de autenticación no devolvió código 1."

    $env:FAKE_RAILWAY_MODE = "unlinked"
    $failureCode = Invoke-SyncExpectFailure -PowerShellPath $powershellExe `
        -ScriptPath (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($failureCode -eq 1) "La falta de enlace no devolvió código 1."

    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $failureCode = Invoke-SyncExpectFailure -PowerShellPath $powershellExe `
        -ScriptPath (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($failureCode -eq 1) "La ausencia del CLI no devolvió código 1."

    Write-Output "sync-railway-stories tests: OK"
}
finally {
    $env:PATH = $originalPath
    Remove-Item Env:FAKE_RAILWAY_SOURCE -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_LOG -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_REPAIR_LOG -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_DELETE_LOG -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_FAIL_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_BULK_TIMEOUT_NAME -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_ARTIFACT_FAIL -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_AGENT_DELETE -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_DELETE_FAIL_NAME -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $testRoot) {
        $resolvedTestRoot = (Resolve-Path -LiteralPath $testRoot).Path
        $resolvedTempRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path
        if ($resolvedTestRoot.StartsWith($resolvedTempRoot) -and
            (Split-Path -Leaf $resolvedTestRoot).StartsWith("asg-railway-sync-test-")) {
            Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
        }
    }
}
