param(
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\18\bin",
    [string]$DatabaseHost = "127.0.0.1",
    [int]$DatabasePort = 5432,
    [string]$DatabaseName = "masterdata",
    [string]$DatabaseUser = "postgres",
    [Parameter(Mandatory = $true)][string]$DatabasePassword
)

$ErrorActionPreference = "Stop"
if ($DatabaseName -notmatch '^[A-Za-z0-9_]+$') { throw "Database name may only contain letters, numbers and underscores." }
$psql = Join-Path $PostgresBin "psql.exe"
$createdb = Join-Path $PostgresBin "createdb.exe"
if (-not (Test-Path $psql)) { throw "psql.exe was not found in $PostgresBin" }

$env:PGPASSWORD = $DatabasePassword
try {
    $exists = & $psql -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DatabaseName'"
    if (($exists | Out-String).Trim() -ne "1") {
        & $createdb -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -E UTF8 $DatabaseName
        if ($LASTEXITCODE -ne 0) { throw "Failed to create database $DatabaseName" }
    }
    & $psql -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -d $DatabaseName -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create PostgreSQL extensions." }
    Write-Host "PostgreSQL database $DatabaseName is ready." -ForegroundColor Green
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
