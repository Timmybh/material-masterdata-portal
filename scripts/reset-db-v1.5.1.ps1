$ErrorActionPreference = "Stop"

$seedFile = Join-Path $PSScriptRoot "..\data\Danh muc vat tu.xlsx"
if (-not (Test-Path $seedFile)) {
    throw "Missing Excel seed: $seedFile. Copy the original 'Danh muc vat tu.xlsx' into the data folder first."
}
$bytes = [System.IO.File]::ReadAllBytes($seedFile)
if ($bytes.Length -lt 4 -or $bytes[0] -ne 0x50 -or $bytes[1] -ne 0x4B -or $bytes[2] -ne 0x03 -or $bytes[3] -ne 0x04) {
    throw "Invalid XLSX file: $seedFile. Save/close the original Excel workbook and copy it again."
}
Write-Host "Excel seed validated: $seedFile" -ForegroundColor Green

Write-Host "WARNING: This will delete the current PostgreSQL volume, users, requests and test data." -ForegroundColor Yellow
$confirm = Read-Host "Type RESET to continue"
if ($confirm -cne "RESET") {
    Write-Host "Cancelled. No data was changed." -ForegroundColor Cyan
    exit 0
}

Write-Host "[1/4] Removing old containers and PostgreSQL volume..." -ForegroundColor Cyan
docker compose down --volumes --remove-orphans

Write-Host "[2/4] Rebuilding V1.5.1 images without cache..." -ForegroundColor Cyan
docker compose build --no-cache

Write-Host "[3/4] Creating the new schema and importing 22,806 material rows..." -ForegroundColor Cyan
docker compose up -d

Write-Host "[4/4] Waiting for database import status..." -ForegroundColor Cyan
docker compose wait db-init
docker compose logs db-init

Write-Host "Database reset command completed." -ForegroundColor Green
