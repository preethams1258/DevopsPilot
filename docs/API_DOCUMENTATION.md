# API quick reference

Interactive OpenAPI docs are at `/docs` when the backend is running.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Register account; first account becomes admin |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Current user |
| GET/POST | `/api/applications` | List/register applications |
| GET/PUT/DELETE | `/api/applications/{id}` | Read/update/delete application |
| POST | `/api/applications/{id}/services` | Register a service |
| DELETE | `/api/applications/services/{service_id}` | Delete a service |
| GET/POST | `/api/applications/{id}/deployments` | List/record deployment history |
| GET | `/api/dashboard/overview` | Dashboard aggregates and Prometheus status |
| GET | `/api/monitoring/metrics` | Prometheus query bundle |
| GET | `/api/monitoring/logs` | Loki logs |
| GET | `/api/monitoring/traces` | Jaeger services |
| POST | `/api/alerts/prometheus` | Alertmanager webhook receiver |
| GET | `/api/incidents` | Incident list |
| POST | `/api/incidents` | Create incident and queue investigation |
| GET | `/api/incidents/{id}` | Incident, evidence and remediation plans |
| GET | `/api/incidents/{id}/timeline` | Incident timeline |
| GET | `/api/incidents/{id}/stream` | SSE updates |
| GET | `/api/incidents/{id}/findings` | Persisted agent runs and retrieved telemetry state |
| POST | `/api/incidents/{id}/investigate` | Re-run investigation |
| GET | `/api/simulator/scenarios` | Supported scenarios |
| POST | `/api/simulator/inject` | Inject named demo scenario |
| POST | `/api/simulator/recover` | Recover named demo scenario |
| GET | `/api/simulator/status` | Read allowlisted demo container status |
| GET | `/api/simulator/status` | Allowlisted container status |
| GET | `/api/remediation/plans` | Remediation plans |
| POST | `/api/remediation/{id}/decision` | Approve/reject; approved action executes |
| POST | `/api/incidents/{id}/verify` | Verify API and DB-dependent product query; update incident status |
| POST | `/api/incidents/{id}/verify` | Verify recovery and update incident status |
| GET | `/api/reports/incidents/{id}` | Structured report data |
| GET | `/api/reports/incidents/{id}/pdf` | PDF download |

All routes except `/health`, auth registration/login/refresh and the Prometheus webhook require a bearer access token. Remediation requires an engineer or admin role.
