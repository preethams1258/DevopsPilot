$ErrorActionPreference = 'Stop'
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
    Write-Host 'Created .env. Edit it now to set unique passwords, JWT_SECRET and CONTROLLER_TOKEN.' -ForegroundColor Yellow
    notepad .env
}
docker compose config | Out-Null
docker compose up --build -d
docker compose ps
Write-Host 'DevOpsPilot UI: http://localhost:5173'
Write-Host 'API docs:       http://localhost:8000/docs'
Write-Host 'Demo shop:      http://localhost:8080'
Write-Host 'Grafana:        http://localhost:3000'
Write-Host 'Jaeger:         http://localhost:16686'
