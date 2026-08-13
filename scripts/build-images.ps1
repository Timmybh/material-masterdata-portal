$ErrorActionPreference='Stop'
docker build -t masterdata-backend:1.5.0 ./backend
docker build -t masterdata-frontend:1.5.0 ./frontend
Write-Host 'Built: masterdata-backend:1.5.0 and masterdata-frontend:1.5.0'
