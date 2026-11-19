"""Evidence-first incident investigation with optional Gemini reasoning."""
from __future__ import annotations
from typing import TypedDict, Any
import json
from app.core.config import settings
from app.observability.clients import prometheus_query, loki_query, jaeger_traces
from app.db.session import SessionLocal
from app.models import Deployment


def record_progress(incident_id: int | None, event_type: str, message: str, details: dict | None = None) -> None:
    if incident_id is None:
        return
    from app.models import IncidentEvent
    db = SessionLocal()
    try:
        db.add(IncidentEvent(incident_id=incident_id, event_type=event_type, message=message, details=details or {}))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


class InvestigationState(TypedDict, total=False):
    incident_id: int
    title: str
    description: str
    severity: str
    logs: dict[str, Any]
    metrics: dict[str, Any]
    traces: dict[str, Any]
    deployments: list[dict[str, Any]]
    affected_service: str
    findings: list[dict[str, Any]]
    root_cause: str
    confidence: float
    remediation: dict[str, Any]
    provider: str
    approval_decision: dict[str, Any]


async def log_analysis(state: InvestigationState) -> InvestigationState:
    try:
        result = await loki_query('{container=~".*monitored-api.*"} |= "error"', 100)
        state["logs"] = result
        state.setdefault("findings", []).append({"agent": "Log Analysis", "source": "Loki", "summary": "Retrieved recent error logs from Loki."})
    except Exception as exc:
        state["logs"] = {"available": False, "error": str(exc)}
        state.setdefault("findings", []).append({"agent": "Log Analysis", "source": "Loki", "summary": "Log source unavailable; no log conclusion made."})
    return state


async def metrics_analysis(state: InvestigationState) -> InvestigationState:
    try:
        import asyncio
        metric_queries = {
            "service_up": "up{job=\"monitored-api\"}",
            "cpu": 'rate(container_cpu_usage_seconds_total{name=~".*monitored-api.*"}[5m])',
            "memory": 'container_memory_working_set_bytes{name=~".*monitored-api.*"}',
            "http_5xx": 'sum(rate(http_requests_total{job="monitored-api",status=~"5.."}[5m]))',
            "p95_latency": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))',
        }
        async def query_one(key, expression):
            try:
                return key, await prometheus_query(expression)
            except Exception as exc:
                return key, {"available": False, "error": str(exc)}
        state["metrics"] = dict(await asyncio.gather(*(query_one(k, q) for k, q in metric_queries.items())))
        state.setdefault("findings", []).append({"agent": "Metrics Analysis", "source": "Prometheus", "summary": "Queried availability, CPU, memory, 5xx rate and p95 latency time series."})
    except Exception as exc:
        state["metrics"] = {"available": False, "error": str(exc)}
        state.setdefault("findings", []).append({"agent": "Metrics Analysis", "source": "Prometheus", "summary": "Metrics source unavailable."})
    return state


async def trace_analysis(state: InvestigationState) -> InvestigationState:
    try:
        state["traces"] = await jaeger_traces()
        state.setdefault("findings", []).append({"agent": "Trace Analysis", "source": "Jaeger", "summary": "Retrieved recent distributed traces for the monitored API."})
    except Exception as exc:
        state["traces"] = {"available": False, "error": str(exc)}
        state.setdefault("findings", []).append({"agent": "Trace Analysis", "source": "Jaeger", "summary": "Trace source unavailable."})
    return state



def deployment_analysis(state: InvestigationState) -> InvestigationState:
    """Correlate recent recorded releases without treating timing alone as proof."""
    application_id = state.get("application_id")
    if not application_id:
        state["deployments"] = []
        state.setdefault("findings", []).append({"agent": "Deployment Investigator", "source": "Platform PostgreSQL", "summary": "No application is linked to this incident; deployment correlation unavailable."})
        return state
    db = SessionLocal()
    try:
        rows = db.query(Deployment).filter(Deployment.application_id == application_id).order_by(Deployment.deployed_at.desc()).limit(10).all()
        state["deployments"] = [{"service": row.service_name, "version": row.version, "previous_version": row.previous_version, "status": row.status, "deployed_at": row.deployed_at.isoformat()} for row in rows]
        summary = f"Retrieved {len(rows)} recent deployment records. Temporal correlation is a clue, not proof of causation."
        state.setdefault("findings", []).append({"agent": "Deployment Investigator", "source": "Platform PostgreSQL", "summary": summary})
    except Exception as exc:
        state["deployments"] = []
        state.setdefault("findings", []).append({"agent": "Deployment Investigator", "source": "Platform PostgreSQL", "summary": f"Deployment history unavailable ({type(exc).__name__})."})
    finally:
        db.close()
    return state


def detection_classification(state: InvestigationState) -> InvestigationState:
    title = (state.get("title", "") + " " + state.get("description", "")).lower()
    if "database" in title or "postgres" in title:
        state["affected_service"] = "demo-postgres"
    elif "latency" in title or "slow" in title:
        state["affected_service"] = "monitored-api"
    elif "cpu" in title:
        state["affected_service"] = "cpu-stressor"
    elif "memory" in title:
        state["affected_service"] = "memory-stressor"
    else:
        state["affected_service"] = "unknown"
    state.setdefault("findings", []).append({"agent": "Detection Agent", "source": "Incident metadata", "summary": f"Classified affected service as {state['affected_service']} based on incident metadata."})
    return state

def grounded_rule_analysis(state: InvestigationState) -> InvestigationState:
    title = (state.get("title", "") + " " + state.get("description", "")).lower()
    if "database" in title or "postgres" in title:
        cause = "The monitored application's database may be unavailable. Confirm with PostgreSQL health and connection-error evidence."
        confidence = 0.65
        action = {"action_type": "start_container", "target": "demo-postgres", "risk": "medium", "reason": "Restore the isolated demo database after confirming it is stopped."}
    elif "latency" in title or "slow" in title:
        cause = "The monitored API may be experiencing elevated response latency. Confirm with Prometheus latency metrics and trace spans."
        confidence = 0.55
        action = {"action_type": "disable_demo_fault", "target": "demo-api", "risk": "low", "reason": "Disable the controlled latency fault in the demo API."}
    elif "cpu" in title:
        cause = "A CPU stress workload may be consuming resources. Confirm with container CPU metrics."
        confidence = 0.55
        action = {"action_type": "stop_container", "target": "cpu-stressor", "risk": "low", "reason": "Stop the isolated CPU stressor."}
    elif "memory" in title:
        cause = "A memory stress workload may be exhausting available memory. Confirm with container memory metrics."
        confidence = 0.55
        action = {"action_type": "stop_container", "target": "memory-stressor", "risk": "low", "reason": "Stop the isolated memory stressor."}
    else:
        cause = "Insufficient evidence to identify a reliable root cause. Review logs, metrics, traces and recent deployments."
        confidence = 0.2
        action = {"action_type": "none", "target": "none", "risk": "low", "reason": "Do not remediate without sufficient evidence."}
    state["root_cause"] = cause
    state["confidence"] = confidence
    state["remediation"] = action
    state["provider"] = "rules"
    return state


async def gemini_refine(state: InvestigationState) -> InvestigationState:
    if not settings.gemini_api_key:
        return grounded_rule_analysis(state)
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import SystemMessage, HumanMessage
        model = ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.gemini_api_key, temperature=0)
        evidence = {key: state.get(key) for key in ("logs", "metrics", "traces", "findings")}
        prompt = "Analyze only supplied evidence. Do not invent observations. If evidence is insufficient, say so. Return JSON with root_cause, confidence (0-1), and remediation (action_type,target,risk,reason). Allowed action_type: start_container, stop_container, disable_demo_fault, none.\n" + json.dumps({"incident": state.get("title"), "description": state.get("description"), "evidence": evidence}, default=str)[:14000]
        result = await model.ainvoke([SystemMessage(content="You are a cautious SRE incident analyst."), HumanMessage(content=prompt)])
        content = result.content if isinstance(result.content, str) else str(result.content)
        parsed = json.loads(content[content.find("{"):content.rfind("}") + 1])
        state["root_cause"] = str(parsed.get("root_cause", "Insufficient evidence"))
        state["confidence"] = max(0.0, min(1.0, float(parsed.get("confidence", 0.2))))
        state["remediation"] = parsed.get("remediation", {"action_type": "none", "target": "none", "risk": "low", "reason": "No safe action proposed."})
        state["provider"] = "gemini"
        return state
    except Exception as exc:
        state = grounded_rule_analysis(state)
        state.setdefault("findings", []).append({"agent": "LLM fallback", "source": "Gemini", "summary": f"Gemini unavailable or returned invalid output; used labelled rule fallback ({type(exc).__name__})."})
        return state



async def investigate(
    payload: dict[str, Any],
    checkpointer=None,
) -> InvestigationState:
    """Execute the LangGraph investigation using the shared checkpointer."""
    from langgraph.graph import StateGraph, START, END

    async def logs_node(state: InvestigationState):
        updated = await log_analysis(state)
        record_progress(
            state.get("incident_id"),
            "agent_completed",
            "Log Analysis Agent queried Loki.",
        )
        return updated

    async def metrics_node(state: InvestigationState):
        updated = await metrics_analysis(state)
        record_progress(
            state.get("incident_id"),
            "agent_completed",
            "Metrics Analysis Agent queried Prometheus.",
        )
        return updated

    async def traces_node(state: InvestigationState):
        updated = await trace_analysis(state)
        record_progress(
            state.get("incident_id"),
            "agent_completed",
            "Trace Analysis Agent queried Jaeger.",
        )
        return updated

    def deployment_node(state: InvestigationState):
        updated = deployment_analysis(state)
        record_progress(
            state.get("incident_id"),
            "agent_completed",
            "Deployment Investigator checked recent release history.",
        )
        return updated

    def detection_node(state: InvestigationState):
        updated = detection_classification(state)
        record_progress(
            state.get("incident_id"),
            "agent_started",
            "Detection Agent classified the incident and affected service.",
            {"affected_service": updated.get("affected_service")},
        )
        return updated

    async def synthesis_node(state: InvestigationState):
        updated = await gemini_refine(state)
        record_progress(
            state.get("incident_id"),
            "diagnosis_ready",
            "Root-cause synthesis completed.",
            {
                "provider": updated.get("provider"),
                "confidence": updated.get("confidence"),
            },
        )
        return updated

    def approval_node(state: InvestigationState):
        from langgraph.types import interrupt

        record_progress(
            state.get("incident_id"),
            "approval_requested",
            "Investigation paused for human remediation approval.",
            {
                "target": state.get("remediation", {}).get("target"),
                "risk": state.get("remediation", {}).get("risk"),
            },
        )

        decision = interrupt({
            "kind": "human_approval_required",
            "incident_id": state.get("incident_id"),
            "root_cause": state.get("root_cause"),
            "confidence": state.get("confidence"),
            "proposed_remediation": state.get("remediation"),
        })

        return {"approval_decision": decision}

    graph = StateGraph(InvestigationState)

    graph.add_node("detection_classification", detection_node)
    graph.add_node("log_analysis", logs_node)
    graph.add_node("metrics_analysis", metrics_node)
    graph.add_node("trace_analysis", traces_node)
    graph.add_node("deployment_analysis", deployment_node)
    graph.add_node("root_cause_synthesis", synthesis_node)

    graph.add_edge(START, "detection_classification")
    graph.add_edge("detection_classification", "log_analysis")
    graph.add_edge("log_analysis", "metrics_analysis")
    graph.add_edge("metrics_analysis", "trace_analysis")
    graph.add_edge("trace_analysis", "deployment_analysis")
    graph.add_edge("deployment_analysis", "root_cause_synthesis")

    if settings.database_url.startswith("postgresql"):
        if checkpointer is None:
            raise RuntimeError(
                "PostgreSQL LangGraph checkpointer was not initialized at application startup."
            )

        graph.add_node("human_approval", approval_node)

        graph.add_conditional_edges(
            "root_cause_synthesis",
            lambda state: (
                "human_approval"
                if state.get("remediation", {}).get("action_type") != "none"
                else "end"
            ),
            {
                "human_approval": "human_approval",
                "end": END,
            },
        )

        graph.add_edge("human_approval", END)

        compiled = graph.compile(checkpointer=checkpointer)
        config = {
            "configurable": {
                "thread_id": str(payload.get("incident_id", "unknown"))
            }
        }

        return await compiled.ainvoke(
            {**payload, "findings": []},
            config=config,
        )

    from langgraph.checkpoint.memory import MemorySaver

    compiled = graph.compile(checkpointer=MemorySaver())
    config = {
        "configurable": {
            "thread_id": str(payload.get("incident_id", "local"))
        }
    }

    return await compiled.ainvoke(
        {**payload, "findings": []},
        config=config,
    )

    from langgraph.graph import StateGraph, START, END

    async def logs_node(state: InvestigationState):
        updated = await log_analysis(state)
        record_progress(state.get("incident_id"), "agent_completed", "Log Analysis Agent queried Loki.")
        return updated

    async def metrics_node(state: InvestigationState):
        updated = await metrics_analysis(state)
        record_progress(state.get("incident_id"), "agent_completed", "Metrics Analysis Agent queried Prometheus.")
        return updated

    async def traces_node(state: InvestigationState):
        updated = await trace_analysis(state)
        record_progress(state.get("incident_id"), "agent_completed", "Trace Analysis Agent queried Jaeger.")
        return updated

    def deployment_node(state: InvestigationState):
        updated = deployment_analysis(state)
        record_progress(state.get("incident_id"), "agent_completed", "Deployment Investigator checked recent release history.")
        return updated

    def detection_node(state: InvestigationState):
        updated = detection_classification(state)
        record_progress(state.get("incident_id"), "agent_started", "Detection Agent classified the incident and affected service.", {"affected_service": updated.get("affected_service")})
        return updated

    async def synthesis_node(state: InvestigationState):
        updated = await gemini_refine(state)
        record_progress(state.get("incident_id"), "diagnosis_ready", "Root-cause synthesis completed.", {"provider": updated.get("provider"), "confidence": updated.get("confidence")})
        return updated

    def approval_node(state: InvestigationState):
        from langgraph.types import interrupt
        record_progress(state.get("incident_id"), "approval_requested", "Investigation paused for human remediation approval.", {"target": state.get("remediation", {}).get("target"), "risk": state.get("remediation", {}).get("risk")})
        decision = interrupt({
            "kind": "human_approval_required",
            "incident_id": state.get("incident_id"),
            "root_cause": state.get("root_cause"),
            "confidence": state.get("confidence"),
            "proposed_remediation": state.get("remediation"),
        })
        return {"approval_decision": decision}

    graph = StateGraph(InvestigationState)
    graph.add_node("detection_classification", detection_node)
    graph.add_node("log_analysis", logs_node)
    graph.add_node("metrics_analysis", metrics_node)
    graph.add_node("trace_analysis", traces_node)
    graph.add_node("deployment_analysis", deployment_node)
    graph.add_node("root_cause_synthesis", synthesis_node)
    graph.add_edge(START, "detection_classification")
    graph.add_edge("detection_classification", "log_analysis")
    graph.add_edge("log_analysis", "metrics_analysis")
    graph.add_edge("metrics_analysis", "trace_analysis")
    graph.add_edge("trace_analysis", "deployment_analysis")
    graph.add_edge("deployment_analysis", "root_cause_synthesis")
    # The durable Postgres graph pauses at a real LangGraph interrupt for human review.
    if settings.database_url.startswith("postgresql"):
        graph.add_node("human_approval", approval_node)
        graph.add_conditional_edges(
            "root_cause_synthesis",
            lambda state: "human_approval" if state.get("remediation", {}).get("action_type") != "none" else "end",
            {"human_approval": "human_approval", "end": END},
        )
        graph.add_edge("human_approval", END)
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        checkpoint_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        async with AsyncPostgresSaver.from_conn_string(checkpoint_url) as checkpointer:
            await checkpointer.setup()
            compiled = graph.compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": str(payload.get("incident_id", "unknown"))}}
            return await compiled.ainvoke({**payload, "findings": []}, config=config)
    # Local SQLite mode is explicitly non-durable and relies on the API approval gate.
    from langgraph.checkpoint.memory import MemorySaver
    compiled = graph.compile(checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": str(payload.get("incident_id", "local"))}}
    return await compiled.ainvoke({**payload, "findings": []}, config=config)



async def resume_approval(
    incident_id: int,
    approved: bool,
    comment: str = "",
    checkpointer=None,
) -> None:
    """Resume a paused Postgres-backed LangGraph run."""

    if not settings.database_url.startswith("postgresql"):
        return

    if checkpointer is None:
        raise RuntimeError(
            "PostgreSQL LangGraph checkpointer is unavailable."
        )

    from langgraph.types import Command
    from langgraph.graph import StateGraph, START, END

    async def noop(state: InvestigationState):
        return state

    def approval_node(state: InvestigationState):
        from langgraph.types import interrupt

        return {
            "approval_decision": interrupt({
                "kind": "human_approval_required",
                "incident_id": incident_id,
            })
        }

    graph = StateGraph(InvestigationState)

    graph.add_node("detection_classification", noop)
    graph.add_node("log_analysis", noop)
    graph.add_node("metrics_analysis", noop)
    graph.add_node("trace_analysis", noop)
    graph.add_node("deployment_analysis", noop)
    graph.add_node("root_cause_synthesis", noop)
    graph.add_node("human_approval", approval_node)

    graph.add_edge(START, "detection_classification")
    graph.add_edge("detection_classification", "log_analysis")
    graph.add_edge("log_analysis", "metrics_analysis")
    graph.add_edge("metrics_analysis", "trace_analysis")
    graph.add_edge("trace_analysis", "deployment_analysis")
    graph.add_edge("deployment_analysis", "root_cause_synthesis")

    graph.add_conditional_edges(
        "root_cause_synthesis",
        lambda state: (
            "human_approval"
            if state.get("remediation", {}).get("action_type") != "none"
            else "end"
        ),
        {
            "human_approval": "human_approval",
            "end": END,
        },
    )

    graph.add_edge("human_approval", END)

    compiled = graph.compile(checkpointer=checkpointer)

    await compiled.ainvoke(
        Command(
            resume={
                "approved": approved,
                "comment": comment,
            }
        ),
        config={
            "configurable": {
                "thread_id": str(incident_id)
            }
        },
    )
