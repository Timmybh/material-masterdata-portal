param(
    [string]$InstallRoot = "C:\Applications\MaterialMasterdataPortal",
    [string]$SiteName = "MaterialMasterdataPortal",
    [int]$SitePort = 8088,
    [string]$PythonExe = "",
    [ValidateRange(2, 8)]
    [int]$WorkerCount = 4
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator."
}

$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backendRoot = Join-Path $InstallRoot "backend"
$frontendRoot = Join-Path $InstallRoot "frontend"
$importSpoolRoot = Join-Path $InstallRoot "import-spool"
$venvRoot = Join-Path $InstallRoot ".venv"
$serviceName = "MaterialMasterdataBackend"
$taskName = "MaterialMasterdataBackend"
$jobsTaskName = "MaterialMasterdataJobs"
$maxUploadBytes = 104857600

$serverManager = Get-Module -ListAvailable -Name ServerManager
if ($serverManager) {
    Import-Module ServerManager
    $features = @("Web-Server", "Web-Static-Content", "Web-Default-Doc", "Web-Http-Errors", "Web-Http-Logging", "Web-Request-Monitor", "Web-Mgmt-Tools")
    Install-WindowsFeature -Name $features | Out-Null
}
else {
    Import-Module Dism
    $features = @(
        "IIS-WebServerRole", "IIS-WebServer", "IIS-CommonHttpFeatures",
        "IIS-DefaultDocument", "IIS-StaticContent", "IIS-HttpErrors",
        "IIS-HealthAndDiagnostics", "IIS-HttpLogging", "IIS-RequestMonitor",
        "IIS-ManagementConsole"
    )
    foreach ($feature in $features) {
        Enable-WindowsOptionalFeature -Online -FeatureName $feature -All -NoRestart | Out-Null
    }
}
Import-Module WebAdministration

$appcmd = Join-Path $env:windir "System32\inetsrv\appcmd.exe"
$modules = (& $appcmd list modules | Out-String)
if ($modules -notmatch "RewriteModule") {
    throw "IIS URL Rewrite is not installed. Install URL Rewrite 2.1 and run this script again."
}
try {
    Get-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" -Filter "system.webServer/proxy" -Name "enabled" | Out-Null
}
catch {
    throw "IIS Application Request Routing (ARR) is not installed. Install ARR and run this script again."
}

foreach ($scheduledTaskName in @($taskName, $jobsTaskName)) {
    $existingTask = Get-ScheduledTask -TaskName $scheduledTaskName -ErrorAction SilentlyContinue
    if ($existingTask -and $existingTask.State -eq "Running") {
        Stop-ScheduledTask -TaskName $scheduledTaskName
    }
}

# Remove the legacy pywin32 service. pywin32 services installed from a virtual
# environment may fail before the application can start under LocalSystem.
$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService) {
    if ($existingService.Status -ne "Stopped") {
        Stop-Service -Name $serviceName -Force
        $existingService.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
    }
    & sc.exe delete $serviceName | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Failed to remove the legacy Windows Service." }
    Start-Sleep -Seconds 1
}

New-Item -ItemType Directory -Force -Path $backendRoot, $frontendRoot, $importSpoolRoot | Out-Null
Copy-Item (Join-Path $sourceRoot "backend\app") $backendRoot -Recurse -Force
Copy-Item (Join-Path $sourceRoot "backend\import_items.py") $backendRoot -Force
Copy-Item (Join-Path $sourceRoot "backend\requirements.txt") $backendRoot -Force
Copy-Item (Join-Path $sourceRoot "backend\logging.json") $backendRoot -Force

$frontendFiles = @("index.html", "app.js", "styles.css", "v16.css", "catalogs.css", "dovitec-logo.png")
foreach ($file in $frontendFiles) {
    Copy-Item (Join-Path $sourceRoot "frontend\$file") $frontendRoot -Force
}
Copy-Item (Join-Path $sourceRoot "deploy\windows\web.config") $frontendRoot -Force
Set-Content -Path (Join-Path $frontendRoot "config.js") -Encoding UTF8 -Value 'window.APP_CONFIG = { API_URL: "/api", GOOGLE_CLIENT_ID: "" };'

if (-not (Test-Path (Join-Path $venvRoot "Scripts\python.exe"))) {
    if ($PythonExe) {
        if (-not (Test-Path $PythonExe)) { throw "Python executable not found: $PythonExe" }
        & $PythonExe -m venv $venvRoot
    }
    else {
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($py) { & $py.Source -3 -m venv $venvRoot }
        else { & python -m venv $venvRoot }
    }
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the Python virtual environment." }
}
$python = Join-Path $venvRoot "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $backendRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Failed to install Python dependencies." }

$envFile = Join-Path $backendRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $sourceRoot ".env.windows.example") $envFile
    Write-Warning "Created $envFile. Update DATABASE_URL, JWT_SECRET and passwords, then run this script again."
    return
}
$envText = Get-Content $envFile -Raw
if ($envText -match "CHANGE_ME|CHANGE_TO_A_LONG_RANDOM_SECRET") {
    throw "File $envFile still contains sample passwords or secrets. Update it before starting the backend."
}

function Set-EnvValue {
    param([string]$Path, [string]$Name, [string]$Value)
    $content = Get-Content $Path -Raw
    $pattern = "(?m)^" + [regex]::Escape($Name) + "=.*$"
    $line = "$Name=$Value"
    if ($content -match $pattern) {
        $content = [regex]::Replace($content, $pattern, $line)
        [System.IO.File]::WriteAllText($Path, $content, (New-Object System.Text.UTF8Encoding($false)))
    }
    else {
        if ($content -and -not $content.EndsWith("`n")) { $content += "`r`n" }
        $content += "$line`r`n"
        [System.IO.File]::WriteAllText($Path, $content, (New-Object System.Text.UTF8Encoding($false)))
    }
}

Set-EnvValue -Path $envFile -Name "RUN_BACKGROUND_JOBS" -Value "false"
Set-EnvValue -Path $envFile -Name "INIT_DB_ON_STARTUP" -Value "false"
Set-EnvValue -Path $envFile -Name "IMPORT_SPOOL_DIR" -Value $importSpoolRoot
Set-EnvValue -Path $envFile -Name "IMPORT_JOB_POLL_SECONDS" -Value "1"
Set-EnvValue -Path $envFile -Name "DB_POOL_SIZE" -Value "5"
Set-EnvValue -Path $envFile -Name "DB_MAX_OVERFLOW" -Value "5"
Set-EnvValue -Path $envFile -Name "DB_POOL_TIMEOUT_SECONDS" -Value "5"
Set-EnvValue -Path $envFile -Name "DB_POOL_RECYCLE_SECONDS" -Value "300"
Set-EnvValue -Path $envFile -Name "DB_CONNECT_TIMEOUT_SECONDS" -Value "5"
Set-EnvValue -Path $envFile -Name "DB_STATEMENT_TIMEOUT_MS" -Value "30000"
Set-EnvValue -Path $envFile -Name "DB_LOCK_TIMEOUT_MS" -Value "5000"

$logsRoot = Join-Path $backendRoot "logs"
$logFile = Join-Path $logsRoot "backend.log"
New-Item -ItemType Directory -Force -Path $logsRoot | Out-Null

Push-Location $backendRoot
try {
    & $python -c "from app.db import init_db; init_db()"
    if ($LASTEXITCODE -ne 0) { throw "Database initialization failed." }
}
finally {
    Pop-Location
}

$webArguments = "-m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers $WorkerCount --proxy-headers --forwarded-allow-ips 127.0.0.1 --log-config logging.json"
$taskAction = New-ScheduledTaskAction -Execute $python -Argument $webArguments -WorkingDirectory $backendRoot
$jobsAction = New-ScheduledTaskAction -Execute $python -Argument "-m app.jobs" -WorkingDirectory $backendRoot
$taskTrigger = New-ScheduledTaskTrigger -AtStartup
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -Principal $taskPrincipal -Description "Material Masterdata Portal FastAPI backend" -Force | Out-Null
Register-ScheduledTask -TaskName $jobsTaskName -Action $jobsAction -Trigger $taskTrigger -Settings $taskSettings -Principal $taskPrincipal -Description "Material Masterdata Portal background jobs" -Force | Out-Null

Set-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" -Filter "system.webServer/proxy" -Name "enabled" -Value "True"
Set-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" -Filter "system.webServer/proxy" -Name "preserveHostHeader" -Value "True"

if (-not (Test-Path "IIS:\AppPools\$SiteName")) {
    New-WebAppPool -Name $SiteName | Out-Null
}
Set-ItemProperty "IIS:\AppPools\$SiteName" -Name managedRuntimeVersion -Value ""
Set-ItemProperty "IIS:\AppPools\$SiteName" -Name processModel.identityType -Value "ApplicationPoolIdentity"
& icacls.exe $frontendRoot /grant "IIS AppPool\${SiteName}:(OI)(CI)RX" /T /C | Out-Null

if (-not (Test-Path "IIS:\Sites\$SiteName")) {
    New-Website -Name $SiteName -Port $SitePort -PhysicalPath $frontendRoot -ApplicationPool $SiteName | Out-Null
}
else {
    Set-ItemProperty "IIS:\Sites\$SiteName" -Name physicalPath -Value $frontendRoot
    Set-ItemProperty "IIS:\Sites\$SiteName" -Name applicationPool -Value $SiteName
}

# ARR reads the request body before forwarding it to FastAPI. Increase both IIS
# request filtering and ARR read-ahead limits so Excel/CSV imports are accepted.
Set-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" -Location $SiteName -Filter "system.webServer/security/requestFiltering/requestLimits" -Name "maxAllowedContentLength" -Value $maxUploadBytes
Set-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" -Location $SiteName -Filter "system.webServer/serverRuntime" -Name "uploadReadAheadSize" -Value $maxUploadBytes

if (-not (Get-NetFirewallRule -DisplayName "Material Masterdata Portal HTTP" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Material Masterdata Portal HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $SitePort | Out-Null
}

Start-ScheduledTask -TaskName $taskName
Start-ScheduledTask -TaskName $jobsTaskName
$backendHealthy = $false
for ($attempt = 1; $attempt -le 60; $attempt++) {
    try {
        $backendHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2
        if ($backendHealth.status -eq "ok") {
            $backendHealthy = $true
            break
        }
    }
    catch { }
    Start-Sleep -Seconds 1
}
if (-not $backendHealthy) {
    if (Test-Path $logFile) { Get-Content $logFile -Tail 50 | Write-Host }
    throw "Backend did not become healthy. Review $logFile."
}
Start-Website -Name $SiteName
Start-Sleep -Seconds 3
$health = Invoke-RestMethod -Uri "http://127.0.0.1:$SitePort/health" -TimeoutSec 15
if ($health.status -ne "ok") { throw "Health check failed." }
Write-Host "Deployment completed: http://localhost:$SitePort" -ForegroundColor Green
