from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models import Application, Service, User, Deployment
from app.schemas.api import ApplicationCreate
from app.core.security import get_current_user

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.post("", status_code=201)
def create_application(payload: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(Application).where(Application.name == payload.name)):
        raise HTTPException(409, "Application name already exists")
    app = Application(**payload.model_dump())
    db.add(app)
    db.commit()
    db.refresh(app)
    return {"id": app.id, "name": app.name, "environment": app.environment, "description": app.description}


@router.get("")
def list_applications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    apps = db.scalars(select(Application).order_by(Application.created_at.desc())).all()
    return [{"id": a.id, "name": a.name, "description": a.description, "environment": a.environment, "services": [{"id": s.id, "name": s.name, "type": s.service_type} for s in a.services]} for a in apps]


@router.get("/{application_id}")
def get_application(application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")
    return {"id": app.id, "name": app.name, "description": app.description, "environment": app.environment, "services": [{"id": s.id, "name": s.name, "type": s.service_type} for s in app.services]}


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")
    db.delete(app)
    db.commit()


@router.put("/{application_id}")
def update_application(application_id: int, payload: ApplicationCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")
    duplicate = db.scalar(select(Application).where(Application.name == payload.name, Application.id != application_id))
    if duplicate:
        raise HTTPException(409, "Application name already exists")
    for key, value in payload.model_dump().items():
        setattr(app, key, value)
    db.commit()
    db.refresh(app)
    return {"id": app.id, "name": app.name, "description": app.description, "environment": app.environment, "health_url": app.health_url}


@router.post("/{application_id}/services", status_code=201)
def add_service(application_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    app = db.get(Application, application_id)
    if not app:
        raise HTTPException(404, "Application not found")
    name = str(payload.get("name", "")).strip()
    if not name or len(name) > 120:
        raise HTTPException(422, "Service name is required and must be at most 120 characters")
    if db.scalar(select(Service).where(Service.application_id == application_id, Service.name == name)):
        raise HTTPException(409, "Service already exists")
    service = Service(application_id=application_id, name=name, service_type=str(payload.get("service_type", "api")), container_name=payload.get("container_name"), health_url=payload.get("health_url"))
    db.add(service)
    db.commit()
    db.refresh(service)
    return {"id": service.id, "name": service.name, "service_type": service.service_type}


@router.delete("/services/{service_id}", status_code=204)
def delete_service(service_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    service = db.get(Service, service_id)
    if not service:
        raise HTTPException(404, "Service not found")
    db.delete(service)
    db.commit()


@router.post("/{application_id}/deployments", status_code=201)
def record_deployment(application_id: int, payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Application, application_id):
        raise HTTPException(404, "Application not found")
    service_name = str(payload.get("service_name", "")).strip()
    version = str(payload.get("version", "")).strip()
    if not service_name or not version:
        raise HTTPException(422, "service_name and version are required")
    deployment = Deployment(application_id=application_id, service_name=service_name, version=version, previous_version=payload.get("previous_version"), status=str(payload.get("status", "succeeded")))
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    return {"id": deployment.id, "service_name": deployment.service_name, "version": deployment.version, "status": deployment.status, "deployed_at": deployment.deployed_at.isoformat()}


@router.get("/{application_id}/deployments")
def list_deployments(application_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not db.get(Application, application_id):
        raise HTTPException(404, "Application not found")
    rows = db.scalars(select(Deployment).where(Deployment.application_id == application_id).order_by(Deployment.deployed_at.desc())).all()
    return [{"id": row.id, "service_name": row.service_name, "version": row.version, "previous_version": row.previous_version, "status": row.status, "deployed_at": row.deployed_at.isoformat()} for row in rows]
