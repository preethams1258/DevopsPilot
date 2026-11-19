# Incident simulator

All scenarios are scoped to the isolated demo application. Confirm the container names in `ALLOWED_DEMO_CONTAINERS` and the controller allowlist before running.

| Scenario | Injection | Recovery |
|---|---|---|
| Database failure | Stop `demo-postgres`, which is separate from platform PostgreSQL | Start `demo-postgres` |
| API latency | Set demo API fault mode to `latency` (4-second delay on product reads) | Set fault mode to `normal` |
| CPU pressure | Run a fixed CPU workload in `cpu-stressor`, maximum 45 seconds | Restart the bounded stressor container |
| Memory pressure | Allocate memory in `memory-stressor`, maximum 45 seconds, 96 MiB container limit | Restart the bounded stressor container |
| Faulty deployment | Switch demo API to controlled `faulty` release mode that returns 500 on product reads | Switch demo API to `normal` |

The faulty deployment scenario currently models a broken release configuration inside the monitored process; it does not yet build and swap a second immutable API image. The failure is real at the API/HTTP layer, but the release mechanism is a controlled configuration switch. Do not describe it as a real image rollback in a project presentation.

## Safety

- No arbitrary commands are accepted by HTTP endpoints or LLM outputs.
- The stress script accepts only `cpu` or `memory` and caps runtime at 60 seconds (the controller sets 45 seconds).
- Docker container targets are checked against a fixed allowlist.
- Never expose the Docker socket proxy or the platform API to a public network.
