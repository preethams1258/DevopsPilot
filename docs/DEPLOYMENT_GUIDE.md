# Local deployment guide

1. Install Docker Desktop and enable WSL2 integration.
2. Copy `.env.example` to `.env` and replace every default password and the JWT secret.
3. Optionally set a Gemini API key.
4. Run `docker compose config` to validate Compose interpolation.
5. Run `docker compose up --build -d`.
6. Wait for `platform-postgres`, `demo-postgres`, and application containers to become healthy.
7. Open the frontend and register the first account.
8. Confirm Prometheus target health, Grafana datasources, Loki labels and Jaeger service traces.

Useful commands:

```powershell
docker compose ps
docker compose logs -f devopspilot-api
docker compose logs -f monitored-api
docker compose down
# Destructive: removes platform/demo databases and observability volumes.
docker compose down -v
```

Do not run `down -v` unless you intend to delete all local project data.
