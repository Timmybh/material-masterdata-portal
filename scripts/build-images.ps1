$ErrorActionPreference='Stop'
docker build -t masterdata-backend:1.5.1 ./backend
docker build -t masterdata-frontend:1.5.1 ./frontend
Write-Host 'Built: masterdata-backend:1.5.1 and masterdata-frontend:1.5.1'
