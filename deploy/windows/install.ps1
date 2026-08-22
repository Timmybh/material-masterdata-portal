param(
    [string]$InstallRoot = "C:\MaterialMasterdata",
    [string]$IisSitePath = "C:\inetpub\wwwroot\material-masterdata"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

New-Item -ItemType Directory -Force -Path $InstallRoot, $IisSitePath, (Join-Path $InstallRoot "logs"), (Join-Path $InstallRoot "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $InstallRoot "backend") | Out-Null
Copy-Item (Join-Path $ProjectRoot "backend\*") (Join-Path $InstallRoot "backend") -Recurse -Force
Copy-Item (Join-Path $ProjectRoot "frontend\*") $IisSitePath -Recurse -Force

if (-not (Test-Path (Join-Path $InstallRoot "python\Scripts\python.exe"))) {
    py -3 -m venv (Join-Path $InstallRoot "python")
}
& (Join-Path $InstallRoot "python\Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $InstallRoot "python\Scripts\python.exe") -m pip install -r (Join-Path $InstallRoot "backend\requirements.txt")

Copy-Item (Join-Path $PSScriptRoot "MaterialMasterdataBackend.xml") (Join-Path $InstallRoot "MaterialMasterdataBackend.xml") -Force
if (-not (Test-Path (Join-Path $InstallRoot ".env"))) {
    Copy-Item (Join-Path $ProjectRoot ".env.example") (Join-Path $InstallRoot ".env")
    Write-Warning "Hãy sửa $InstallRoot\.env trước khi khởi động service."
}
Copy-Item (Join-Path $InstallRoot ".env") (Join-Path $InstallRoot "backend\.env") -Force

$WinSw = Join-Path $InstallRoot "MaterialMasterdataBackend.exe"
if (-not (Test-Path $WinSw)) {
    throw "Thiếu WinSW tại $WinSw. Tải WinSW x64, đổi tên thành MaterialMasterdataBackend.exe rồi chạy lại."
}
& $WinSw stop 2>$null
& $WinSw uninstall 2>$null
& $WinSw install
& $WinSw start
Write-Host "Đã cài backend service. Cấu hình IIS trỏ Physical Path đến $IisSitePath."
