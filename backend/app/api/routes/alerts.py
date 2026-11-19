from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import Incident, IncidentEvent, Application
from app.api.routes.incidents import run_investigation

router = APIRouter(prefix="/api/alerts", tags=["alert ingestion"])


@router.post("/prometheus", status_code=202)
async def prometheus_alert(request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    payload = await request.json()
    alerts = payload.get("alerts", [])
    accepted = 0
    for alert in alerts:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        title = labels.get("alertname", "Prometheus alert")
        status = alert.get("status", "firing")
        if status == "resolved":
            continue
        fingerprint = alert.get("fingerprint", title)
        existing = db.scalar(select(Incident).where(Incident.title == f"{title} [{fingerprint}]").where(Incident.status.notin_(["resolved", "closed"])))
        if existing:
            continue
        demo_app = db.scalar(select(Application).where(Application.name == "DevOpsPilot Demo Shop"))
        incident = Incident(title=f"{title} [{fingerprint}]", description=annotations.get("description", annotations.get("summary", "Alert received from Prometheus.")), severity="critical" if labels.get("severity") == "critical" else "warning", source="prometheus", application_id=demo_app.id if demo_app else None)
        db.add(incident)
        db.flush()
        db.add(IncidentEvent(incident_id=incident.id, event_type="alert_received", message="Prometheus alert received.", details={"labels": labels, "annotations": annotations}))
        db.flush()
        background.add_task(run_investigation, incident.id)
        accepted += 1
    db.commit()
    return {"accepted": accepted}
