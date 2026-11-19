from fastapi import APIRouter, Depends, HTTPException,Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user, require_roles
from app.models import User, Incident, IncidentEvent, RemediationPlan, Approval, RemediationExecution, AuditLog, Application, SimulatorExecution, Deployment
from app.simulator.controller import simulator, controller, ControllerError
from app.observability.clients import collect_telemetry, prometheus_query, loki_query, jaeger_services
from app.schemas.api import ApprovalRequest
from app.core.config import settings
from app.agents.workflow import resume_approval
import httpx

router = APIRouter(prefix="/api", tags=["platform"])


@router.get("/dashboard/overview")
async def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    incidents = db.scalars(select(Incident).order_by(Incident.created_at.desc()).limit(8)).all()
    telemetry = await collect_telemetry()
    all_incidents = db.scalars(select(Incident)).all()
    application_count = len(db.scalars(select(Application)).all())
    return {"active_incidents": sum(i.status not in {"resolved", "closed"} for i in all_incidents), "critical_incidents": sum(i.severity == "critical" and i.status != "resolved" for i in all_incidents), "applications": application_count, "telemetry": telemetry, "recent_incidents": [{"id": i.id, "title": i.title, "severity": i.severity, "status": i.status} for i in incidents]}


@router.get("/monitoring/metrics")
async def metrics(user: User = Depends(get_current_user)):
    return await collect_telemetry()


@router.get("/monitoring/logs")
async def logs(user: User = Depends(get_current_user)):
    try:
        return await loki_query('{container=~".*monitored-api.*"}', 100)
    except Exception as exc:
        raise HTTPException(503, f"Loki unavailable: {exc}") from exc


@router.get("/monitoring/traces")
async def traces(user: User = Depends(get_current_user)):
    try:
        return await jaeger_services()
    except Exception as exc:
        raise HTTPException(503, f"Jaeger unavailable: {exc}") from exc


@router.get("/simulator/scenarios")
def scenarios(user: User = Depends(get_current_user)):
    return simulator.SCENARIOS


@router.post("/simulator/inject")
def inject(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "engineer"))):
    scenario = str(payload.get("scenario", ""))
    try:
        result = simulator.inject(scenario)
        db.add(SimulatorExecution(scenario=scenario, target=result.get("name", "monitored-api"), action="inject", status="success", result=result))
        if scenario == "faulty_deployment":
            demo_app = db.scalar(select(Application).where(Application.name == "DevOpsPilot Demo Shop"))
            if demo_app:
                db.add(Deployment(application_id=demo_app.id, service_name="monitored-api", version="demo-faulty-release", previous_version="demo-stable", status="failed"))
        db.add(AuditLog(user_id=user.id, action="simulator_inject", resource_type="scenario", resource_id=scenario, details=result))
        db.commit()
        return result
    except (ControllerError, httpx.HTTPError) as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/simulator/recover")
def recover(payload: dict, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "engineer"))):
    scenario = str(payload.get("scenario", ""))
    try:
        result = simulator.recover(scenario)
        db.add(SimulatorExecution(scenario=scenario, target=result.get("name", "monitored-api"), action="recover", status="success", result=result))
        if scenario == "faulty_deployment":
            demo_app = db.scalar(select(Application).where(Application.name == "DevOpsPilot Demo Shop"))
            if demo_app:
                db.add(Deployment(application_id=demo_app.id, service_name="monitored-api", version="demo-stable", previous_version="demo-faulty-release", status="rolled_back"))
        db.add(AuditLog(user_id=user.id, action="simulator_recover", resource_type="scenario", resource_id=scenario, details=result))
        db.commit()
        return result
    except (ControllerError, httpx.HTTPError) as exc:
        raise HTTPException(503, str(exc)) from exc


@router.get("/simulator/status")
def simulator_status(user: User = Depends(get_current_user)):
    result = {}
    for name in settings.allowed_containers:
        try:
            result[name] = controller.status(name)
        except Exception as exc:
            result[name] = {"available": False, "error": str(exc)}
    return result


@router.get("/remediation/plans")
def plans(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(RemediationPlan).order_by(RemediationPlan.created_at.desc())).all()
    return [{"id": p.id, "incident_id": p.incident_id, "action_type": p.action_type, "target": p.target, "reason": p.reason, "risk": p.risk, "status": p.status} for p in rows]



@router.post("/remediation/{plan_id}/decision")
async def decide(
    plan_id: int,
    payload: ApprovalRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "engineer")),
):
    plan = db.get(RemediationPlan, plan_id)

    if not plan:
        raise HTTPException(404, "Plan not found")

    if (
        plan.status != "awaiting_approval"
        or db.scalar(select(Approval).where(Approval.plan_id == plan_id))
    ):
        raise HTTPException(409, "This plan already has a decision")

    checkpointer = request.app.state.checkpointer

    approval = Approval(
        plan_id=plan_id,
        user_id=user.id,
        decision=payload.decision,
        comment=payload.comment,
    )
    db.add(approval)

    if payload.decision == "reject":
        plan.status = "rejected"
        incident = db.get(Incident, plan.incident_id)

        incident.status = "remediation_rejected"
        db.add(IncidentEvent(
            incident_id=incident.id,
            event_type="remediation_rejected",
            message="Human reviewer rejected the proposed remediation.",
        ))
        db.add(AuditLog(
            user_id=user.id,
            action="remediation_rejected",
            resource_type="plan",
            resource_id=str(plan_id),
        ))
        db.commit()

        try:
            await resume_approval(
                plan.incident_id,
                False,
                payload.comment,
                checkpointer,
            )
        except Exception as exc:
            db.add(AuditLog(
                user_id=user.id,
                action="graph_resume_failed",
                resource_type="plan",
                resource_id=str(plan_id),
                details={"error": str(exc)},
            ))
            db.commit()

        return {"status": "rejected"}

    # Execute only explicitly allowlisted actions.
    try:
        db.commit()

        await resume_approval(
            plan.incident_id,
            True,
            payload.comment,
            checkpointer,
        )

        if plan.action_type == "start_container" and plan.target == "demo-postgres":
            result = controller.start("demo-postgres")

        elif (
            plan.action_type == "stop_container"
            and plan.target in {"cpu-stressor", "memory-stressor"}
        ):
            result = controller.stop(plan.target)

        elif (
            plan.action_type == "disable_demo_fault"
            and plan.target == "demo-api"
        ):
            response = httpx.post(
                f"{settings.monitored_api_url}/demo/fault",
                json={"mode": "normal"},
                timeout=5,
            )
            response.raise_for_status()
            result = response.json()

        else:
            raise ControllerError(
                "Action is not in the remediation allowlist"
            )

        plan.status = "executed"
        db.add(RemediationExecution(
            plan_id=plan.id,
            status="success",
            result=result,
        ))

        incident = db.get(Incident, plan.incident_id)
        incident.status = "verifying"

        db.add(IncidentEvent(
            incident_id=incident.id,
            event_type="remediation_executed",
            message="Approved remediation executed.",
            details=result,
        ))
        db.add(AuditLog(
            user_id=user.id,
            action="remediation_executed",
            resource_type="plan",
            resource_id=str(plan_id),
            details=result,
        ))

        db.commit()

        return {
            "status": "executed",
            "result": result,
            "verification": "pending",
        }

    except Exception as exc:
        db.rollback()

        plan = db.get(RemediationPlan, plan_id)
        plan.status = "execution_failed"

        failed_incident = db.get(Incident, plan.incident_id)
        failed_incident.status = "remediation_failed"

        db.add(IncidentEvent(
            incident_id=failed_incident.id,
            event_type="remediation_failed",
            message="Approved remediation could not be executed.",
            details={"error": str(exc)},
        ))
        db.add(RemediationExecution(
            plan_id=plan.id,
            status="failed",
            result={"error": str(exc)},
        ))

        db.commit()

        raise HTTPException(
            503,
            f"Remediation failed: {exc}",
        ) from exc


@router.post("/incidents/{incident_id}/verify")
async def verify(incident_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    incident = db.get(Incident, incident_id)
    if not incident:
        raise HTTPException(404, "Incident not found")
    checks = {"api_health": False, "database_dependent_products": False}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            health = await client.get(f"{settings.monitored_api_url}/health")
            products = await client.get(f"{settings.monitored_api_url}/products")
        checks["api_health"] = health.status_code == 200 and health.json().get("status") == "healthy"
        checks["database_dependent_products"] = products.status_code == 200 and isinstance(products.json(), list)
    except Exception as exc:
        checks["error"] = str(exc)
    healthy = checks["api_health"] and checks["database_dependent_products"]
    if healthy:
        incident.status = "resolved"
        db.add(IncidentEvent(incident_id=incident_id, event_type="resolved", message="API health and database-dependent product query passed.", details=checks))
    else:
        incident.status = "reopened"
        db.add(IncidentEvent(incident_id=incident_id, event_type="verification_failed", message="One or more recovery checks failed; incident remains open.", details=checks))
    db.commit()
    return {"healthy": healthy, "checks": checks, "status": incident.status}
