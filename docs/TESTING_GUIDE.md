# Testing guide

## Automated backend tests

Run `cd backend; pytest -q`. Tests cover password hashing, malformed hashes, allowlist rejection, fixed stressor action validation and conservative fallback behavior.

## Docker integration checks

- `docker compose config` succeeds.
- `GET http://localhost:8000/health` returns healthy.
- `GET http://localhost:8001/health` returns healthy and database connected.
- Prometheus targets show `monitored-api` and `cadvisor` UP.
- Loki returns container logs for the demo API.
- Jaeger lists `monitored-api` after browsing the shop and generating requests.
- Inject each simulator scenario and observe actual behavior.
- Ensure recovery restores the demo shop.
- Verify the incident only resolves after a successful monitored API health check.

## Evaluation dataset

Record each run with scenario ID, injected timestamp, detection timestamp, known fault ground truth, agent hypothesis, supporting evidence, approved action, execution result, and verification result. Compute detection latency, RCA correctness, evidence precision, remediation success and verification correctness from those recorded runs. Do not publish unmeasured accuracy percentages.
