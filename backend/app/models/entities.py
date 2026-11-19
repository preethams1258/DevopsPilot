from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db.session import Base


JSONType = JSON().with_variant(JSONB, "postgresql")


def now_utc():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="engineer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    environment: Mapped[str] = mapped_column(String(40), default="demo")
    health_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    services: Mapped[list["Service"]] = relationship(back_populates="application", cascade="all, delete-orphan")


class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    service_type: Mapped[str] = mapped_column(String(60), default="api")
    container_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    health_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    application: Mapped[Application] = relationship(back_populates="services")
    __table_args__ = (UniqueConstraint("application_id", "name", name="uq_service_app_name"),)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    status: Mapped[str] = mapped_column(String(30), default="detected", index=True)
    source: Mapped[str] = mapped_column(String(40), default="manual")
    application_id: Mapped[int | None] = mapped_column(ForeignKey("applications.id"), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    events: Mapped[list["IncidentEvent"]] = relationship(back_populates="incident", cascade="all, delete-orphan")


class IncidentEvent(Base):
    __tablename__ = "incident_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    incident: Mapped[Incident] = relationship(back_populates="events")


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(30), default="running")
    provider: Mapped[str] = mapped_column(String(30), default="rules")
    state: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class EvidenceRecord(Base):
    __tablename__ = "evidence_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RemediationPlan(Base):
    __tablename__ = "remediation_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(20), default="medium")
    plan_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="awaiting_approval")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("remediation_plans.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RemediationExecution(Base):
    __tablename__ = "remediation_executions"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("remediation_plans.id", ondelete="CASCADE"), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict] = mapped_column(JSONType, default=dict)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[str] = mapped_column(String(80), default="")
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Environment(Base):
    __tablename__ = "environments"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(40), default="demo")
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    __table_args__ = (UniqueConstraint("application_id", "name", name="uq_environment_app_name"),)


class Deployment(Base):
    __tablename__ = "deployments"
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    service_name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(120))
    previous_version: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="succeeded")
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class SimulatorExecution(Base):
    __tablename__ = "simulator_executions"
    id: Mapped[int] = mapped_column(primary_key=True)
    scenario: Mapped[str] = mapped_column(String(60))
    target: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30))
    result: Mapped[dict] = mapped_column(JSONType, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RootCauseHypothesis(Base):
    __tablename__ = "root_cause_hypotheses"
    id: Mapped[int] = mapped_column(primary_key=True)
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    hypothesis: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(default=0.0)
    supporting_evidence: Mapped[dict] = mapped_column(JSONType, default=dict)
    contradicting_evidence: Mapped[dict] = mapped_column(JSONType, default=dict)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    permissions: Mapped[list] = mapped_column(JSONType, default=list)


class ServiceDependency(Base):
    __tablename__ = "service_dependencies"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    target_service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"))
    dependency_type: Mapped[str] = mapped_column(String(40), default="calls")
    __table_args__ = (UniqueConstraint("source_service_id", "target_service_id", name="uq_service_dependency"),)
