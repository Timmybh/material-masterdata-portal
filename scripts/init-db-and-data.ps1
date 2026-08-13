$ErrorActionPreference = "Stop"

Write-Host "[1/4] Starting PostgreSQL on port 5432..." -ForegroundColor Cyan
docker compose up -d postgres

Write-Host "[2/4] Building database initializer..." -ForegroundColor Cyan
docker compose build db-init

Write-Host "[3/4] Creating schema, FTS indexes and importing seed data..." -ForegroundColor Cyan
docker compose run --rm db-init

Write-Host "[4/4] Database is ready." -ForegroundColor Green
Write-Host "Host     : localhost"
Write-Host "Port     : 5432"
Write-Host "Database : masterdata"
Write-Host "User     : postgres"
Write-Host "Password : 12345678"
