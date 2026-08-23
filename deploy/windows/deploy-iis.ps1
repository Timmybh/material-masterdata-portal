param(
    [string]$InstallRoot = "C:\Apps\MaterialMasterdataPortal",
    [string]$SiteName = "MaterialMasterdataPortal",
    [int]$SitePort = 8088
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Hãy mở PowerShell bằng Run as Administrator."
}

$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$backendRoot = Join-Path $InstallRoot "backend"
$frontendRoot = Join-Path $InstallRoot "frontend"
$venvRoot = Join-Path $InstallRoot ".venv"
$serviceName = "MaterialMasterdataBackend"

Import-Module ServerManager
$features = @("Web-Server", "Web-Static-Content", "Web-Default-Doc", "Web-Http-Errors", "Web-Http-Logging", "Web-Request-Monitor", "Web-Mgmt-Tools")
Install-WindowsFeature -Name $features | Out-Null
Import-Module WebAdministration

$appcmd = Join-Path $env:windir "System32\inetsrv\appcmd.exe"
$modules = (& $appcmd list modules | Out-String)
if ($modules -notmatch "RewriteModule") {
    throw "IIS URL Rewrite chưa được cài. Cài URL Rewrite 2.1 rồi chạy lại script."
}
try {
    Get-WebConfigurationProperty -PSPath "MACHINE/WEBROOT/APPHOST" -Filter "system.webServer/proxy" -Name "enabled" | Out-Null
}
catch {
    throw "IIS Application Request Routing (ARR) chưa được cài. Cài ARR rồi chạy lại script."
}

$existingService = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($existingService -and $existingService.Status -ne "Stopped") {
    Stop-Service -Name $serviceName -Force
    $existingService.WaitForStatus("Stopped", [TimeSpan]::FromSeconds(30))
}

New-Item -ItemType Directory -Force -Path $backendRoot, $frontendRoot | Out-Null
Copy-Item (Join-Path $sourceRoot "backend\app") $backendRoot -Recurse -Force
Copy-Item (Join-Path $sourceRoot "backend\import_items.py") $backendRoot -Force
Copy-Item (Join-Path $sourceRoot "backend\requirements.txt") $backendRoot -Force
Copy-Item (Join-Path $sourceRoot "backend\windows_service.py") $backendRoot -Force

$frontendFiles = @("index.html", "app.js", "styles.css", "v16.css", "catalogs.css", "dovitec-logo.png")
foreach ($file in $frontendFiles) {
    Copy-Item (Join-Path $sourceRoot "frontend\$file") $frontendRoot -Force
}
Copy-Item (Join-Path $sourceRoot "deploy\windows\web.config") $frontendRoot -Force
Set-Content -Path (Join-Path $frontendRoot "config.js") -Encoding UTF8 -Value 'window.APP_CONFIG = { API_URL: "/api", GOOGLE_CLIENT_ID: "" };'

if (-not (Test-Path (Join-Path $venvRoot "Scripts\python.exe"))) {
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) { & $py.Source -3 -m venv $venvRoot }
    else { & python -m venv $venvRoot }
}
$python = Join-Path $venvRoot "Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -r (Join-Path $backendRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Cài Python dependencies thất bại" }

$envFile = Join-Path $backendRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $sourceRoot ".env.windows.example") $envFile
    Write-Warning "Đã tạo $envFile. Hãy sửa DATABASE_URL, JWT_SECRET và mật khẩu rồi chạy lại script."
    return
}
$envText = Get-Content $envFile -Raw
if ($envText -match "CHANGE_ME|CHANGE_TO_A_LONG_RANDOM_SECRET") {
    throw "File $envFile vẫn còn mật khẩu/secret mẫu. Hãy cập nhật trước khi cài service."
}

Push-Location $backendRoot
try {
    if ($existingService) {
        & $python windows_service.py --startup auto update
    }
    else {
        & $python windows_service.py --startup auto install
    }
    if ($LASTEXITCODE -ne 0) { throw "Không thể cài Windows Service" }
}
finally { Pop-Location }
& sc.exe failure $serviceName reset= 86400 actions= restart/5000/restart/15000/restart/60000 | Out-Null
& sc.exe failureflag $serviceName 1 | Out-Null

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

Start-Service -Name $serviceName
Start-Website -Name $SiteName
Start-Sleep -Seconds 3
$health = Invoke-RestMethod -Uri "http://127.0.0.1:$SitePort/health" -TimeoutSec 15
if ($health.status -ne "ok") { throw "Health check không thành công" }
Write-Host "Triển khai thành công: http://localhost:$SitePort" -ForegroundColor Green
