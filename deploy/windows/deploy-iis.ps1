param(
    [string]$InstallRoot = "C:\Apps\MaterialMasterdataPortal",
    [string]$SiteName = "MaterialMasterdataPortal",
    [int]$SitePort = 8088,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run PowerShell as Administrator."
}

$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backendRoot = Join-Path $InstallRoot "backend"
$frontendRoot = Join-Path $InstallRoot "frontend"
$venvRoot = Join-Path $InstallRoot ".venv"
$serviceName = "MaterialMasterdataBackend"
$taskName = "MaterialMasterdataBackend"

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

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask -and $existingTask.State -eq "Running") {
    Stop-ScheduledTask -TaskName $taskName
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

New-Item -ItemType Directory -Force -Path $backendRoot, $frontendRoot | Out-Null
Copy-Item (Join-Path $sourceRoot "backend\app") $backendRoot -Recurse -Force
Copy-Item (Join-Path $sourceRoot "backend\import_items.py") $backendRoot -Force
Copy-Item (Join-Path $sourceRoot "backend\requirements.txt") $backendRoot -Force

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

$logsRoot = Join-Path $backendRoot "logs"
$logFile = Join-Path $logsRoot "backend.log"
$launcher = Join-Path $backendRoot "start-backend.cmd"
New-Item -ItemType Directory -Force -Path $logsRoot | Out-Null
$launcherText = @"
@echo off
cd /d "$backendRoot"
"$python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1 >> "$logFile" 2>&1
"@
Set-Content -Path $launcher -Encoding ASCII -Value $launcherText

$taskAction = New-ScheduledTaskAction -Execute $env:ComSpec -Argument "/d /c `"`"$launcher`"`""
$taskTrigger = New-ScheduledTaskTrigger -AtStartup
$taskSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $taskTrigger -Settings $taskSettings -Principal $taskPrincipal -Description "Material Masterdata Portal FastAPI backend" -Force | Out-Null

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

if (-not (Get-NetFirewallRule -DisplayName "Material Masterdata Portal HTTP" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "Material Masterdata Portal HTTP" -Direction Inbound -Action Allow -Protocol TCP -LocalPort $SitePort | Out-Null
}

Start-ScheduledTask -TaskName $taskName
$backendHealthy = $false
for ($attempt = 1; $attempt -le 30; $attempt++) {
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
