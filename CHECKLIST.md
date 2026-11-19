# DevOpsPilot AI implementation checklist

Status meanings: **Implemented** = source code/configuration exists; **Sandbox-tested** = automated check passed in this workspace; **Laptop verification** = depends on Docker/Windows infrastructure and has not been proven here; **Not implemented** = still required.

## Platform foundation
- [x] Monorepo structure, environment template, `.gitignore`, README
- [x] FastAPI application and OpenAPI docs
- [x] SQLAlchemy schema: 18 declared tables
- [x] Startup schema creation and demo application seeding
- [x] Alembic configuration and initial schema revision (review migration strategy before evolving schema)
- [x] JWT access/refresh tokens, PBKDF2 password hashing, first-user admin bootstrap
- [x] Viewer/engineer/admin role string and protected route role checks
- [x] Login/register rate limit (single-process local-demo limiter; use Redis-backed limiter for multi-worker deployment)
- [x] Audit records for account registration, simulator actions and remediation decisions/execution
- [ ] Full user/role administration UI and permission matrix
- [ ] Full application update/service CRUD and environment management UI

## Monitored application and observability
- [x] Demo shop browser frontend
- [x] FastAPI demo API with products, health, orders and controlled fault modes
- [x] Separate demo PostgreSQL and platform PostgreSQL
- [x] Prometheus scrape config and alert rules
- [x] Alertmanager webhook config and incident ingestion endpoint
- [x] cAdvisor service for container metrics
- [x] Loki config and Promtail Docker log discovery
- [x] OpenTelemetry FastAPI instrumentation and Collector config
- [x] Jaeger all-in-one tracing service and query client
- [x] Grafana datasource provisioning and starter dashboard
- [ ] Docker Compose observability integration verified on Windows laptop
- [ ] Confirm Promtail labels and Loki queries against actual Docker Desktop logs
- [ ] Confirm traces appear in Jaeger on Docker Desktop

## Simulator and restricted controller
- [x] Separate infrastructure-controller microservice with bearer-token authentication
- [x] Writable Docker socket proxy isolated from the platform API; Promtail uses a separate read-only proxy
- [x] Controller validates exact allowlisted container names
- [x] No user-supplied shell command interface
- [x] Database failure injection/recovery targets only demo PostgreSQL
- [x] API latency injection/recovery
- [x] Bounded CPU workload (45-second controller duration, 0.5 CPU, 128 MiB limit)
- [x] Bounded memory workload (45-second controller duration, 96 MiB limit)
- [x] Faulty release configuration injection/recovery (controlled failing API mode; not an immutable image rollback)
- [x] Simulator execution and audit persistence
- [ ] Actual Docker socket-proxy and fault/recovery behavior verified on laptop
- [ ] Immutable image-based faulty deployment and rollback (not implemented; current demo uses a real failing API release mode)

## Agentic investigation
- [x] LangGraph state graph with detection, logs, metrics, traces, deployment and synthesis nodes
- [x] Loki, Prometheus and Jaeger query clients
- [x] Optional Gemini integration with evidence-only prompt and JSON extraction
- [x] Explicitly labelled deterministic fallback when Gemini is absent/fails
- [x] Root-cause confidence and structured remediation proposal
- [x] PostgreSQL LangGraph checkpointer configuration for Compose; MemorySaver for local SQLite
- [x] LangGraph human approval interrupt in PostgreSQL mode and resume function
- [x] Investigation result and evidence summary persistence
- [ ] LangGraph/Postgres checkpoint and interrupt/resume verified on laptop
- [ ] Agent evaluation dataset and measured RCA/precision metrics
- [ ] More robust JSON schema validation/retry and model provider adapter tests
- [ ] Deployment history ingestion UI/API (table and agent read path exist; full deployment workflow is not implemented)

## Incident lifecycle and reporting
- [x] Manual incident creation and Prometheus alert ingestion
- [x] Incident list/detail/timeline and SSE endpoint with agent progress events
- [x] Background investigation execution
- [x] One approval per plan and one execution per plan database constraints
- [x] Exact remediation action/target allowlist
- [x] Audit trail and remediation result persistence
- [x] API and database-dependent product-query verification; resolves only when both pass, otherwise reopens
- [x] PDF incident report endpoint and UI download
- [ ] End-to-end alert → investigation → approval → remediation → verification tested on laptop
- [ ] PDF layout/content reviewed with actual evidence data

## Frontend
- [x] React + TypeScript + Vite shell and responsive dark UI
- [x] Login/register/logout
- [x] Dashboard and telemetry connectivity summary
- [x] Application list and registration
- [x] Incident list/detail modal, re-investigation and verification action
- [x] Five-scenario simulator UI
- [x] Approval/rejection UI
- [x] Incident report PDF download UI
- [x] SSE stream wired into incident detail modal with live agent progress/timeline events
- [ ] Rich metrics charts and full agent-by-agent live progress visualization
- [ ] Frontend production build and browser E2E test (requires npm dependency install)

## Quality, docs and delivery
- [x] Unit tests for security, controller allowlist, fallback and API auth/application CRUD
- [x] Architecture, schema, agent, API, simulator, deployment, testing, demo and interview docs
- [x] Python syntax compilation
- [x] TypeScript/JSX syntax transpilation check
- [ ] Ruff lint (Ruff is not installed in this workspace)
- [ ] Docker Compose config/build/runtime verification (Docker unavailable in this workspace)
- [ ] Playwright end-to-end tests
- [ ] Performance/resource test on target laptop

## Sandbox verification results
- `pytest -q` from repository root: **11 passed** (8 backend tests and 3 controller safety tests)
- `python -m compileall -q backend controller-service monitored-app/backend`: passed
- TypeScript transpile syntax check for App, main, API client and Vite config: passed
- YAML parse and network-isolation checks for Compose, Prometheus, Loki, Promtail, OTel Collector, Alertmanager and Grafana configuration: passed
- Dependency installation could not complete because this sandbox has no package-network access; LangGraph and Gemini runtime integration therefore remain unexecuted here.
- Docker and Playwright are unavailable in this sandbox. Never interpret laptop-verification items as passed.
