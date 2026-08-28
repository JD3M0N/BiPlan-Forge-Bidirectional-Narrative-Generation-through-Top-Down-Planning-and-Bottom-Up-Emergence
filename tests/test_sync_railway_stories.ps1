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
    $name = ($remotePath.Replace("\", "/") -split "/")[-1]
    Add-Content -LiteralPath $env:FAKE_RAILWAY_LOG -Value $name
    New-Item -ItemType Directory -Path $localPath -Force | Out-Null
    Copy-Item -Path (Join-Path (Join-Path $env:FAKE_RAILWAY_SOURCE $name) "*") `
        -Destination $localPath -Recurse -Force
    if ($name -eq $env:FAKE_RAILWAY_FAIL_NAME) { exit 9 }
    Write-Output '{"ok":true}'
    exit 0
}
exit 2
'@
    Set-Content -LiteralPath (Join-Path $fakeBin "railway.ps1") `
        -Value $fakeRailway -Encoding UTF8

    $existing = Join-Path $testRepo "Stories\Top-Down\existing-run"
    $existingRemote = Join-Path $fakeRemote "existing-run"
    $newRemote = Join-Path $fakeRemote "new-run"
    New-Item -ItemType Directory -Path $existing, $existingRemote, $newRemote -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $existing "local-marker.txt") -Value "local"
    Set-Content -LiteralPath (Join-Path $existingRemote "story.md") -Value "remote story"
    Set-Content -LiteralPath (Join-Path $newRemote "story.md") -Value "new story"

    $env:PATH = "$fakeBin;$originalPath"
    $env:FAKE_RAILWAY_SOURCE = $fakeRemote
    $env:FAKE_RAILWAY_LOG = Join-Path $testRoot "downloads.log"
    $env:FAKE_RAILWAY_MODE = ""
    $env:FAKE_RAILWAY_FAIL_NAME = ""

    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 0) "La sincronización inicial falló."
    Assert-True (Test-Path (Join-Path $testRepo "Stories\Top-Down\new-run\story.md")) `
        "No se descargó la ejecución nueva."
    Assert-True ((Get-Content (Join-Path $existing "local-marker.txt")) -eq "local") `
        "Se modificó una ejecución local existente."
    Assert-True (-not (Test-Path (Join-Path $testRepo "Stories\.railway-sync"))) `
        "No se limpió el staging después del éxito."

    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 0) "La segunda sincronización falló."
    Assert-True (@(Get-Content $env:FAKE_RAILWAY_LOG).Count -eq 1) `
        "Se volvió a descargar una ejecución existente."

    $failedRemote = Join-Path $fakeRemote "failed-run"
    New-Item -ItemType Directory -Path $failedRemote -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $failedRemote "story.md") -Value "partial"
    $env:FAKE_RAILWAY_FAIL_NAME = "failed-run"
    & $powershellExe -NoProfile -ExecutionPolicy Bypass -File `
        (Join-Path $testRepo "sync-railway-stories.ps1")
    Assert-True ($LASTEXITCODE -eq 1) "Una descarga fallida no devolvió código 1."
    Assert-True (-not (Test-Path (Join-Path $testRepo "Stories\Top-Down\failed-run"))) `
        "Una descarga fallida dejó una carpeta final incompleta."

    $env:FAKE_RAILWAY_FAIL_NAME = ""
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
    Remove-Item Env:FAKE_RAILWAY_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_RAILWAY_FAIL_NAME -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $testRoot) {
        $resolvedTestRoot = (Resolve-Path -LiteralPath $testRoot).Path
        $resolvedTempRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path
        if ($resolvedTestRoot.StartsWith($resolvedTempRoot) -and
            (Split-Path -Leaf $resolvedTestRoot).StartsWith("asg-railway-sync-test-")) {
            Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
        }
    }
}
