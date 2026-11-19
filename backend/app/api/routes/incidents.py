from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db, SessionLocal
from app.models import Incident, IncidentEvent, AgentRun, EvidenceRecord, RemediationPlan, RootCauseHypothesis, User, Application
from app.schemas.api import IncidentCreate
from app.core.security import get_current_user
from app.agents.workflow import investigate
import hashlib, json

router = APIRouter(prefix="/api/incidents", tags=["incidents"])



async def run_investigation(incident_id: int, checkpointer=None):
    db = SessionLocal()
    try:
        incident = db.get(Incident, incident_id)
        if not incident:
            return

        incident.status = "investigating"
        db.add(
            IncidentEvent(
                incident_id=incident.id,
                event_type="investigation_started",
                message="LangGraph investigation started.",
            )
        )
        db.commit()

        result = await investigate(
            {
                "incident_id": incident.id,
                "application_id": incident.application_id,
                "title": incident.title,
                "description": incident.description,
                "severity": incident.severity,
            },
            checkpointer=checkpointer,
        )

        incident.root_cause = result.get("root_cause")
        incident.confidence = result.get("confidence")
        incident.status = (
            "awaiting_approval"
            if result.get("remediation", {}).get("action_type") != "none"
            else "diagnosis_ready"
        )

        safe_state = {
            key: value
            for key, value in result.items()
            if key != "__interrupt__"
        }
        safe_state = json.loads(json.dumps(safe_state, default=str))

        run = AgentRun(
            incident_id=incident.id,
            status="awaiting_approval" if result.get("__interrupt__") else "completed",
            provider=result.get("provider", "rules"),
            state=safe_state,
        )
        db.add(run)

        db.add(
            RootCauseHypothesis(
                incident_id=incident.id,
                hypothesis=result.get("root_cause", "Insufficient evidence"),
                confidence=float(result.get("confidence", 0.0)),
                supporting_evidence={"findings": result.get("findings", [])},
                contradicting_evidence={},
                selected=True,
            )
        )

        for finding in result.get("findings", []):
            db.add(
                EvidenceRecord(
                    incident_id=incident.id,
                    source=finding.get("source", "agent"),
                    summary=finding.get("summary", ""),
                    payload=finding,
                )
            )

        action = result.get("remediation", {})
        if action.get("action_type") != "none":
            plan_data = {"incident_id": incident.id, **action}
            plan_hash = hashlib.sha256(
                json.dumps(plan_data, sort_keys=True).encode()
            ).hexdigest()

            if not db.scalar(
                select(RemediationPlan).where(
                    RemediationPlan.plan_hash == plan_hash
                )
            ):
                db.add(
                    RemediationPlan(
                        incident_id=incident.id,
                        action_type=action["action_type"],
                        target=action["target"],
                        reason=action["reason"],
                        risk=action.get("risk", "medium"),
                        plan_hash=plan_hash,
                    )
                )

        db.add(
            IncidentEvent(
                incident_id=incident.id,
                event_type="investigation_completed",
                message="Evidence collection and root-cause analysis completed.",
                details={
                    "provider": result.get("provider"),
                    "confidence": result.get("confidence"),
                },
            )
        )
        db.commit()

    except Exception as exc:
        db.rollback()
        incident = db.get(Incident, incident_id)
        if incident:
            incident.status = "investigation_failed"
            db.add(
                IncidentEvent(
                    incident_id=incident_id,
                    event_type="investigation_failed",
                    message=str(exc)[:500],
                )
            )
            db.commit()

    finally:
        db.close()




@router.post("", status_code=201)
def create_incident(
    payload: IncidentCreate,
    background: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if payload.severity not in {"info", "warning", "critical"}:
        raise HTTPException(422, "Severity must be info, warning or critical")

    incident_data = payload.model_dump()

    if incident_data.get("application_id") is None:
        demo_app = db.scalar(
            select(Application).where(
                Application.name == "DevOpsPilot Demo Shop"
            )
        )
        incident_data["application_id"] = demo_app.id if demo_app else None

    incident = Incident(**incident_data)
    db.add(incident)
    db.commit()
    db.refresh(incident)

    db.add(
        IncidentEvent(
            incident_id=incident.id,
            event_type="detected",
            message="Incident created.",
        )
    )
    db.commit()

    background.add_task(
        run_investigation,
        incident.id,
        request.app.state.checkpointer,
    )

    return {
        "id": incident.id,
        "status": incident.status,
        "title": incident.title,
    }


@router.get("")
def list_incidents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.scalars(select(Incident).order_by(Incident.created_at.desc()).limit(200)).all()
    return [{"id": i.id, "title": i.title, "severity": i.severity, "status": i.status, "root_cause": i.root_cause, "confidence": i.confidence, "created_at": i.created_at.isoformat()} for i in items]


@router.get("/{incident_id}")
def get_incident(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    i = db.get(Incident, incident_id)
    if not i:
        raise HTTPException(404, "Incident not found")
    plans = db.scalars(select(RemediationPlan).where(RemediationPlan.incident_id == i.id)).all()
    evidence = db.scalars(select(EvidenceRecord).where(EvidenceRecord.incident_id == i.id)).all()
    latest_run = db.scalar(select(AgentRun).where(AgentRun.incident_id == i.id).order_by(AgentRun.created_at.desc()))
    return {"id": i.id, "title": i.title, "description": i.description, "severity": i.severity, "status": i.status, "root_cause": i.root_cause, "confidence": i.confidence, "plans": [{"id": p.id, "action_type": p.action_type, "target": p.target, "reason": p.reason, "risk": p.risk, "status": p.status} for p in plans], "evidence": [{"source": e.source, "summary": e.summary, "payload": e.payload} for e in evidence], "events": [{"type": e.event_type, "message": e.message, "created_at": e.created_at.isoformat()} for e in i.events], "investigation": latest_run.state if latest_run else None}


@router.get("/{incident_id}/timeline")
def timeline(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Incident, incident_id):
        raise HTTPException(404, "Incident not found")
    events = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == incident_id).order_by(IncidentEvent.created_at)).all()
    return [{"type": e.event_type, "message": e.message, "details": e.details, "created_at": e.created_at.isoformat()} for e in events]



@router.post("/{incident_id}/investigate")
def reinvestigate(
    incident_id: int,
    background: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    incident = db.get(Incident, incident_id)

    if not incident:
        raise HTTPException(404, "Incident not found")

    incident.status = "investigating"
    db.commit()

    background.add_task(
        run_investigation,
        incident_id,
        request.app.state.checkpointer,
    )

    return {
        "status": "investigation_queued",
        "incident_id": incident_id,
    }



@router.get("/{incident_id}/stream")
async def stream_incident(incident_id: int, user: User = Depends(get_current_user)):
    """Server-sent event stream for incident status/timeline updates."""
    import asyncio
    import json
    from fastapi.responses import StreamingResponse

    check_db = SessionLocal()
    try:
        exists = check_db.get(Incident, incident_id) is not None
    finally:
        check_db.close()
    if not exists:
        raise HTTPException(404, "Incident not found")

    async def events():
        last_signature = None
        for _ in range(120):
            db = SessionLocal()
            try:
                incident = db.get(Incident, incident_id)
                if not incident:
                    yield f"event: error\ndata: {json.dumps({'detail': 'Incident not found'})}\n\n"
                    return
                event_rows = db.scalars(select(IncidentEvent).where(IncidentEvent.incident_id == incident_id).order_by(IncidentEvent.created_at)).all()
                payload = {"status": incident.status, "root_cause": incident.root_cause, "confidence": incident.confidence, "events": [{"type": e.event_type, "message": e.message, "created_at": e.created_at.isoformat()} for e in event_rows]}
                signature = json.dumps(payload, sort_keys=True)
                if signature != last_signature:
                    yield f"event: incident_update\ndata: {json.dumps(payload)}\n\n"
                    last_signature = signature
                if incident.status in {"resolved", "closed", "investigation_failed", "diagnosis_ready", "remediation_rejected"}:
                    return
            finally:
                db.close()
            await asyncio.sleep(2)
        yield "event: timeout\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/{incident_id}/findings")
def findings(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Incident, incident_id):
        raise HTTPException(404, "Incident not found")
    runs = db.scalars(select(AgentRun).where(AgentRun.incident_id == incident_id).order_by(AgentRun.created_at.desc())).all()
    return [{"id": run.id, "status": run.status, "provider": run.provider, "state": run.state, "created_at": run.created_at.isoformat()} for run in runs]
