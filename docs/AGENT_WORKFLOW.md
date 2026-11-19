# Agent workflow

1. Detection classification identifies a likely affected service from incident metadata.
2. Log analysis queries Loki for monitored API errors.
3. Metrics analysis queries Prometheus for availability, CPU, memory, 5xx rate and p95 latency.
4. Trace analysis retrieves recent Jaeger traces for `monitored-api`.
5. Deployment investigation retrieves recent recorded release history for the linked application; time correlation is not treated as proof.
6. Root-cause synthesis uses Gemini when configured, with a strict evidence-only prompt and validated JSON output. Without Gemini, a labelled deterministic fallback is used.
7. A structured remediation plan is persisted. In Postgres mode, LangGraph checkpoints the state and pauses at a real `interrupt()` approval node.
8. The human approval endpoint records the decision and resumes the graph. The controller separately validates and executes the approved exact action.
9. Verification checks the monitored API `/health` endpoint. The incident resolves only after a passing health check; otherwise it reopens.

## Evidence discipline

Unavailable telemetry is represented as unavailable. It is not fabricated. Rule fallback confidence is deliberately conservative. A title-based scenario classification is a demo convenience, not a substitute for evidence. The Gemini prompt requires the model to state uncertainty when evidence is insufficient.

## Durability

Docker Compose uses `AsyncPostgresSaver` and an incident ID thread key. Local SQLite development uses `MemorySaver` and is not durable across process restarts.
