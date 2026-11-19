from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user
from app.models import Incident, IncidentEvent, EvidenceRecord, RemediationPlan, Approval, RemediationExecution, User
from app.reports.pdf import build_incident_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])


def data_for(incident_id: int, db: Session):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    evidence = db.scalars(select(EvidenceRecord).where(EvidenceRecord.incident_id == incident_id).order_by(EvidenceRecord.observed_at)).all()
    plans = db.scalars(select(RemediationPlan).where(RemediationPlan.incident_id == incident_id)).all()
    events = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == incident_id).order_by(IncidentEvent.created_at)).all()
    plan_data = []
    for plan in plans:
        approval = db.scalar(select(Approval).where(Approval.plan_id == plan.id))
        execution = db.scalar(select(RemediationExecution).where(RemediationExecution.plan_id == plan.id))
        reviewer = db.get(User, approval.user_id) if approval else None
        plan_data.append({
            "id": plan.id, "action_type": plan.action_type, "target": plan.target,
            "reason": plan.reason, "risk": plan.risk, "status": plan.status,
            "approval": {"decision": approval.decision, "comment": approval.comment, "reviewer": reviewer.email if reviewer else "unknown", "created_at": approval.created_at.isoformat()} if approval else None,
            "execution": {"status": execution.status, "result": execution.result, "executed_at": execution.executed_at.isoformat()} if execution else None,
        })
    return {
        "id": incident.id, "title": incident.title, "description": incident.description,
        "severity": incident.severity, "status": incident.status,
        "root_cause": incident.root_cause, "confidence": incident.confidence,
        "created_at": incident.created_at.isoformat(), "updated_at": incident.updated_at.isoformat(),
        "evidence": [{"source": e.source, "summary": e.summary, "payload": e.payload} for e in evidence],
        "plans": plan_data,
        "timeline": [{"type": e.event_type, "message": e.message, "details": e.details, "created_at": e.created_at.isoformat()} for e in events],
    }


@router.get("/incidents/{incident_id}")
def report(incident_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return data_for(incident_id, db)


@router.get("/incidents/{incident_id}/pdf")
def report_pdf(incident_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    pdf = build_incident_pdf(data_for(incident_id, db))
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=incident-{incident_id}.pdf"})
