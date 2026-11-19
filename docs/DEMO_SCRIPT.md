# Six-step capstone demonstration

1. **Healthy application:** open DevOpsPilot, the demo shop, Prometheus and Jaeger. Show healthy DB-backed product requests, metrics, logs and traces.
2. **Database failure:** inject database failure. Demonstrate that only the demo PostgreSQL container stops and shop product requests fail.
3. **AI investigation:** create or inspect the incident. Show actual Loki, Prometheus and Jaeger retrieval, findings, deployment context and RCA uncertainty/confidence.
4. **Remediation:** inspect the proposed action and risk. Approve it from the UI. Show the persisted approval and restricted controller execution.
5. **Verification:** confirm demo PostgreSQL is available, API `/health` succeeds and product requests recover. Resolve only after the health check.
6. **Report:** download the incident PDF and show its evidence, diagnosis, approval, action and verification record.

This is one continuous end-to-end scenario, not six separate apps.
