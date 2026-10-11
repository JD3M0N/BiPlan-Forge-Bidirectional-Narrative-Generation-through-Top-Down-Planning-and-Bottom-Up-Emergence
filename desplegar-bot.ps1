<#
.SYNOPSIS
    Instala todo lo necesario y deja el bot de Telegram del estudio funcionando en esta PC.
.DESCRIPTION
    Un solo paso para la PC que sirve el bot (lo lanza iniciar-bot.bat con doble clic):
    instala Python 3.12 si no hay 3.12 ni 3.15, crea el entorno, completa .env, crea el estudio pack,
    evita la suspension y registra una tarea que arranca el bot al iniciar sesion y lo
    reinicia si se cae. Se puede repetir sin romper nada.
.EXAMPLE
    .\desplegar-bot.ps1
.EXAMPLE
    .\desplegar-bot.ps1 -Estado
.EXAMPLE
    .\desplegar-bot.ps1 -Desinstalar
#>
[CmdletBinding()]
param(
    [switch]$Ejecutar,
    [switch]$Estado,
    [switch]$Desinstalar,
    [switch]$Actualizar,
    [string]$Estudio = "Evaluations/telegram-pack/study.sqlite3"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$TaskName = "StageCraft Telegram"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$LogDir = Join-Path $Root "Stories"
$Log = Join-Path $LogDir "telegram-bot.log"
$EnvFile = Join-Path $Root ".env"
$AuthorPrompts = Join-Path $Root "apps\telegram\pack_author_prompts.json"
$PythonInstaller = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
$Required = [ordered]@{
    "TELEGRAM_BOT_TOKEN" = "Token del bot (te lo da @BotFather)"
    "TELEGRAM_ACCESS_KEY" = "Clave que escribiran los participantes para entrar"
    "GEMINI_API_KEY" = "Clave de la API de Gemini"
    "TELEGRAM_ADMIN_IDS" = "ID numerico de Telegram del investigador (lo da @userinfobot)"
}

function Write-Step([string]$Text) {
    Write-Host ""
    Write-Host "==> $Text" -ForegroundColor Cyan
}

function Stop-Bot {
    # The task's supervisor and its Python child must both go before pip touches the venv.
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    }
    $venv = (Join-Path $Root ".venv").ToLowerInvariant()
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLowerInvariant().StartsWith($venv) -and $_.CommandLine -match "asg_telegram" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

function Read-EnvFile {
    $values = [ordered]@{}
    if (Test-Path -LiteralPath $EnvFile) {
        foreach ($line in [IO.File]::ReadAllLines($EnvFile)) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
                $values[$Matches[1]] = $Matches[2].Trim()
            }
        }
    }
    return $values
}

function Set-EnvValue([string]$Key, [string]$Value) {
    $lines = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $EnvFile) { $lines.AddRange([IO.File]::ReadAllLines($EnvFile)) }
    $found = $false
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^\s*$Key\s*=") { $lines[$i] = "$Key=$Value"; $found = $true }
    }
    if (-not $found) { $lines.Add("$Key=$Value") }
    [IO.File]::WriteAllLines($EnvFile, $lines, [Text.UTF8Encoding]::new($false))
}

function Find-SupportedPython {
    # Accepts 3.12 or 3.15, the two versions with checked constraints; 3.12 first.
    # Probing writes to stderr when a version is missing; that must not stop the script.
    $ErrorActionPreference = "Continue"
    $check = 'import sys; sys.exit(0 if sys.version_info[:2] in ((3, 12), (3, 15)) and sys.maxsize > 2**32 else 1)'
    $candidates = @()
    foreach ($version in "312", "315") {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Python\Python$version\python.exe")
        $candidates += "C:\Program Files\Python$version\python.exe"
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($version in "-3.12", "-3.15") {
            $found = & py $version -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $found) { $candidates = @("$found".Trim()) + $candidates; break }
        }
    }
    $onPath = Get-Command python -ErrorAction SilentlyContinue
    if ($onPath) { $candidates += $onPath.Source }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            & $candidate -c $check 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        }
    }
    return $null
}

function Install-Python312 {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Instalando Python 3.12 con winget..."
        & winget install --id Python.Python.3.12 --exact --scope user --silent `
            --accept-package-agreements --accept-source-agreements
        $python = Find-SupportedPython
        if ($python) { return $python }
    }
    Write-Host "Descargando el instalador oficial de Python 3.12..."
    $installer = Join-Path $env:TEMP "python-3.12-amd64.exe"
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $PythonInstaller -OutFile $installer -UseBasicParsing
    $process = Start-Process -FilePath $installer -Wait -PassThru -ArgumentList @(
        "/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_test=0"
    )
    if ($process.ExitCode -ne 0) { throw "El instalador de Python termino con codigo $($process.ExitCode)." }
    $python = Find-SupportedPython
    if (-not $python) { throw "Python 3.12 no aparece tras instalarlo. Instalalo a mano desde python.org y repite." }
    return $python
}

function Invoke-Supervisor {
    # Keeps the bot alive inside the scheduled task: restart on any exit, one copy at a time.
    $mutex = [Threading.Mutex]::new($false, "Local\StageCraftTelegramBot")
    try {
        if (-not $mutex.WaitOne(0)) { return }
    } catch [Threading.AbandonedMutexException] {
        # A previous supervisor died holding it; the mutex is now ours.
    }
    $ErrorActionPreference = "Continue"
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    Set-Location -LiteralPath $Root
    while ($true) {
        if ((Test-Path -LiteralPath $Log) -and (Get-Item -LiteralPath $Log).Length -gt 20MB) {
            Move-Item -LiteralPath $Log -Destination "$Log.1" -Force
        }
        Add-Content -LiteralPath $Log -Encoding UTF8 -Value "`n=== Arranque $(Get-Date -Format s) ==="
        & cmd.exe /c "`"$VenvPython`" -u -m asg_telegram.app >> `"$Log`" 2>&1"
        $code = $LASTEXITCODE
        Add-Content -LiteralPath $Log -Encoding UTF8 -Value "=== El bot termino con codigo $code $(Get-Date -Format s) ==="
        # Exit code 2 is a configuration error: retrying fast would only fill the log.
        Start-Sleep -Seconds $(if ($code -eq 2) { 300 } else { 30 })
    }
}

function Register-BotTask {
    $arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Ejecutar"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $Root
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description "Bot de Telegram del estudio StageCraft" -Force | Out-Null
}

function Show-Status {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) { Write-Host "Tarea '$TaskName': $($task.State)" } else { Write-Host "La tarea no esta registrada." }
    if (Test-Path -LiteralPath $Log) {
        Write-Host "Ultimas lineas de $Log :"
        Get-Content -LiteralPath $Log -Tail 25 -Encoding UTF8
    }
}

Set-Location -LiteralPath $Root
if ($Ejecutar) { Invoke-Supervisor; return }
if ($Estado) { Show-Status; return }
if ($Desinstalar) {
    Stop-Bot
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Bot detenido y tarea eliminada. Los datos de Stories/ y Evaluations/ siguen intactos." -ForegroundColor Green
    return
}

Write-Step "Deteniendo el bot si ya estaba en marcha"
Stop-Bot

if ($Actualizar -and (Test-Path -LiteralPath (Join-Path $Root ".git")) -and (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Step "Actualizando el codigo"
    & git -C $Root pull --ff-only
    if ($LASTEXITCODE -ne 0) { Write-Warning "No se pudo actualizar con git; sigo con el codigo actual." }
}

Write-Step "Comprobando Python (3.12 o 3.15)"
$python = Find-SupportedPython
if (-not $python) { $python = Install-Python312 }
Write-Host "Python: $python"

Write-Step "Instalando dependencias (puede tardar varios minutos la primera vez)"
& (Join-Path $Root "setup.ps1") -Telegram -Python $python

Write-Step "Configurando .env"
$values = Read-EnvFile
foreach ($key in $Required.Keys) {
    if (-not $values[$key]) {
        Write-Host "Falta $key. $($Required[$key])." -ForegroundColor Yellow
        do { $answer = (Read-Host "  $key").Trim() } while (-not $answer)
        Set-EnvValue $key $answer
    }
}
if ($values["ASG_PROJECT_ROOT"] -and ([IO.Path]::GetFullPath($values["ASG_PROJECT_ROOT"]) -ne [IO.Path]::GetFullPath($Root))) {
    Write-Host "ASG_PROJECT_ROOT apuntaba a otra PC; lo dejo vacio."
    Set-EnvValue "ASG_PROJECT_ROOT" ""
}
Set-EnvValue "ASG_EVALUATION_STUDY" $Estudio

Write-Step "Preparando el estudio"
$studyPath = Join-Path $Root $Estudio
$studyTool = Join-Path $Root ".venv\Scripts\evaluation-study.exe"
$studyReady = $false
if (Test-Path -LiteralPath $studyPath) {
    $studyReady = & {
        $ErrorActionPreference = "Continue"
        & $studyTool --db $studyPath status *> $null
        $LASTEXITCODE -eq 0
    }
    if (-not $studyReady) {
        # An interrupted earlier run left a database without a study; keep it aside, never delete.
        Move-Item -LiteralPath $studyPath -Destination "$studyPath.incompleto-$(Get-Date -Format yyyyMMddHHmmss)"
    }
}
if (-not $studyReady) {
    $version = (& $VenvPython -c "from asg_stagecraft.version import GENERATOR_VERSION; print(GENERATOR_VERSION)").Trim()
    & $studyTool --db $studyPath create telegram-pack --version $version --mode pack --author-prompts $AuthorPrompts
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el estudio." }
    & $studyTool --db $studyPath collect | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "No se pudo abrir la recogida del estudio." }
    Write-Host "Estudio creado en $Estudio y abierto a la recogida."
} else {
    Write-Host "El estudio ya existe; se conserva tal cual con sus datos."
}

Write-Step "Evitando que el equipo se suspenda mientras este enchufado"
try {
    & powercfg /change standby-timeout-ac 0
    & powercfg /change hibernate-timeout-ac 0
} catch {
    Write-Warning "No se pudo cambiar la energia; desactiva la suspension a mano en Configuracion."
}

Write-Step "Registrando el arranque automatico"
Register-BotTask
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 20
$alive = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "asg_telegram" }
if ($alive) {
    Write-Host ""
    Write-Host "El bot esta funcionando. Prueba /start desde Telegram." -ForegroundColor Green
} else {
    Write-Warning "El bot no sigue en marcha. Revisa el registro:"
    Show-Status
}
Write-Host ""
Write-Host "Arrancara solo cada vez que se inicie sesion en este usuario, y se reinicia si se cae."
Write-Host "Deja la PC encendida, con la sesion iniciada y con Internet."
Write-Host "  Ver estado y registro:  iniciar-bot.bat -Estado"
Write-Host "  Detener y desinstalar:  iniciar-bot.bat -Desinstalar"
Write-Host "  Registro completo:      $Log"
