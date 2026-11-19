# Database schema

The SQLAlchemy metadata defines 18 tables:

| Table | Purpose |
|---|---|
| users | Accounts, password hashes, active state and role name |
| roles | Role catalogue and permission metadata |
| applications | Registered monitored applications |
| environments | Per-application deployment environments |
| services | Application service inventory |
| service_dependencies | Directed service dependency edges |
| incidents | Incident lifecycle, severity and RCA summary |
| incident_events | Append-only incident timeline entries |
| agent_runs | LangGraph run status, provider and persisted result summary |
| evidence_records | Source and concise evidence references |
| root_cause_hypotheses | Ranked hypothesis and evidence summary |
| deployments | Version and release history |
| remediation_plans | Exact action, target, reason, risk and immutable plan hash |
| approvals | One human decision per plan |
| remediation_executions | One execution record per plan |
| simulator_executions | Fault injection and recovery history |
| notifications | User-facing notifications |
| audit_logs | Security and operational audit trail |

JSON columns store structured evidence and configuration; core relationships and identifiers remain relational. Alembic is configured under `backend/migrations`. The current initial migration uses metadata creation; review and generate a conventional frozen migration before schema changes or production-like deployment.
