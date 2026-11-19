from app.reports.pdf import build_incident_pdf


def test_incident_pdf_contains_pdf_header():
    payload = {
        "id": 42, "title": "Database failure", "severity": "critical", "status": "resolved",
        "description": "Demo DB was unavailable", "root_cause": "Demo postgres container stopped", "confidence": 0.9,
        "created_at": "2026-11-16T10:00:00+00:00", "updated_at": "2026-11-16T10:02:00+00:00",
        "evidence": [{"source": "Loki", "summary": "Database connection refused"}],
        "plans": [{"action_type": "start_container", "target": "demo-postgres", "reason": "Restore demo database", "risk": "medium", "status": "executed", "approval": None, "execution": None}],
        "timeline": [{"type": "detected", "message": "Incident detected", "created_at": "2026-11-16T10:00:00+00:00"}],
    }
    pdf = build_incident_pdf(payload)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 500
