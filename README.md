# DevOpsPilot AI

**Agentic incident investigation and human-approved remediation for an isolated demo environment.**

DevOpsPilot collects application telemetry, groups incidents, retrieves logs/metrics/traces, runs a LangGraph investigation, prepares a remediation proposal, requires a human decision, executes a narrow allowlisted action, and verifies recovery before resolving an incident.

> This is a local engineering capstone, not a production incident-management product. Never connect the simulator to production systems. The Docker socket proxies are privileged infrastructure; the writable proxy is isolated on a dedicated internal network and reachable only by the restricted infrastructure-controller service. Promtail uses a separate read-only proxy. Run this Compose project only on a machine/environment dedicated to the demo.

## Architecture

- **Platform API:** FastAPI, SQLAlchemy, PostgreSQL, JWT authentication and role checks.
- **Agent workflow:** LangGraph state graph, Loki/Prometheus/Jaeger evidence retrieval, optional Gemini synthesis, explicitly labelled deterministic fallback.
- **Telemetry:** Prometheus + cAdvisor metrics, Loki + Promtail container logs, OpenTelemetry Collector + Jaeger traces, Grafana dashboards/datasources.
- **Demo target:** separate e-commerce API + PostgreSQL and browser UI.
- **Simulator:** five controlled scenarios. Database faults affect only `demo-postgres`; CPU and memory workloads are bounded and resource-limited; latency and faulty-release modes are toggled only on the demo API.
- **Remediation:** a separate restricted infrastructure-controller service is the only application allowed to reach the Docker socket proxy. The platform API calls its narrow authenticated endpoints; exact allowlisted actions, one approval per plan, one execution per plan, audit trail and health-check verification are enforced.

## Requirements

- Docker Desktop with Compose v2, preferably 16 GB RAM (8 GB may require stopping some observability services).
- Windows 10/11 with WSL2 backend recommended.
- Gemini API key is optional. Without it, the labelled rule-based fallback still investigates known demo cases; it must not be described as an LLM result.

## Start on Windows

Open PowerShell in this folder:

```powershell
Copy-Item .env.example .env
notepad .env
```

Set unique local passwords and a long random `JWT_SECRET`. Add `GEMINI_API_KEY` if available. Do not commit `.env`.

```powershell
docker compose config
docker compose up --build -d
docker compose ps
```

Open:

- DevOpsPilot UI: http://localhost:5173
- API docs: http://localhost:8000/docs
- Demo shop: http://localhost:8080
- Demo API: http://localhost:8001/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin / value of `GRAFANA_PASSWORD`)
- Jaeger: http://localhost:16686
- Alertmanager: http://localhost:9093

Register the first account in DevOpsPilot; it becomes `admin`. Later accounts become `engineer`. Use a password of at least 10 characters.

## First end-to-end check

1. Open the demo shop and verify products load.
2. Open DevOpsPilot and register the first user.
3. Go to Incident Simulator and inject **Database failure**.
4. Confirm the demo shop fails to load products and check API logs/Prometheus targets.
5. Create an incident titled `Database failure` (or wait for Prometheus alert ingestion if alert rules fire).
6. Inspect the incident and its evidence. The investigation uses live telemetry APIs when available.
7. Review the generated remediation plan in Approvals and approve it. Only the allowlisted `demo-postgres` start action is accepted.
8. Verify recovery from the incident workflow/API; the incident is resolved only if `/health` passes.
9. Export the incident PDF from `GET /api/reports/incidents/{id}/pdf` (authenticated).

## Simulator safety

- The demo PostgreSQL database is separate from the platform PostgreSQL database.
- The API accepts scenario identifiers, not shell commands or arbitrary container names.
- The controller allowlists container names and exact action/target pairs.
- CPU and memory workloads run in separate containers with Docker resource limits and a 45-second maximum workload duration.
- A human approval is required for remediation; a unique plan hash and unique database constraints prevent duplicate decisions/executions.
- The Compose stack mounts a Docker socket through a socket proxy. That still grants powerful local infrastructure access. Do not expose the proxy or API to untrusted networks.

## Development without Docker

Backend:

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL="sqlite:///./devopspilot.db"
$env:JWT_SECRET="local-development-secret-change-this"
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

The observability queries and simulator require the Compose services. The full stack is the supported demo mode.

## Tests

Backend tests (from repository root; install backend requirements first):

```powershell
pip install -r backend/requirements.txt
pytest -q
```

Or run backend tests inside the Compose API container:

```powershell
docker compose exec devopspilot-api pytest -q
```

Restricted controller safety tests (local Python environment):

```powershell
cd controller-service
pip install -r requirements.txt
pip install pytest
pytest -q
```

Local backend tests can also be run from `backend` after installing requirements:

```bash
pytest -q
```

## Important limitations to validate locally

- This workspace cannot launch Docker Desktop or verify container fault injection. Compose, socket-proxy behavior, cAdvisor, Promtail, Prometheus alert delivery, and actual recovery must be tested on the target laptop.
- The initial Alembic migration uses SQLAlchemy metadata creation. For long-lived deployments, replace it with a fully generated, reviewed migration revision before schema evolution.
- SSE/live agent progress, full role/permission administration, and rich service dependency maps are not yet implemented in this initial integrated codebase; see `CHECKLIST.md`.
