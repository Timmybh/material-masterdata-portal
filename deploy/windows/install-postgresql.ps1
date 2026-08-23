param(
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\16\bin",
    [string]$DatabaseHost = "127.0.0.1",
    [int]$DatabasePort = 5432,
    [string]$DatabaseName = "masterdata",
    [string]$DatabaseUser = "postgres",
    [Parameter(Mandatory = $true)][string]$DatabasePassword
)

$ErrorActionPreference = "Stop"
if ($DatabaseName -notmatch '^[A-Za-z0-9_]+$') { throw "Tên database chỉ được chứa chữ, số và dấu gạch dưới." }
$psql = Join-Path $PostgresBin "psql.exe"
$createdb = Join-Path $PostgresBin "createdb.exe"
if (-not (Test-Path $psql)) { throw "Không tìm thấy psql.exe tại $PostgresBin" }

$env:PGPASSWORD = $DatabasePassword
try {
    $exists = & $psql -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DatabaseName'"
    if (($exists | Out-String).Trim() -ne "1") {
        & $createdb -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -E UTF8 $DatabaseName
        if ($LASTEXITCODE -ne 0) { throw "Không thể tạo database $DatabaseName" }
    }
    & $psql -h $DatabaseHost -p $DatabasePort -U $DatabaseUser -d $DatabaseName -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"
    if ($LASTEXITCODE -ne 0) { throw "Không thể tạo PostgreSQL extensions" }
    Write-Host "PostgreSQL database $DatabaseName đã sẵn sàng." -ForegroundColor Green
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}
