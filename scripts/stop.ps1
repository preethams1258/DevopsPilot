$ErrorActionPreference = 'Stop'
docker compose down
Write-Host 'Containers stopped. Volumes and database data were preserved.'
