"""Narrow infrastructure execution boundary. Only this service can reach the Docker proxy."""
import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

TOKEN = os.getenv("CONTROLLER_TOKEN", "")
ALLOWED = {x.strip() for x in os.getenv("ALLOWED_DEMO_CONTAINERS", "demo-postgres,cpu-stressor,memory-stressor").split(",") if x.strip()}
DOCKER_BASE_URL = os.getenv("DOCKER_BASE_URL", "tcp://docker-proxy:2375")
app = FastAPI(title="DevOpsPilot Restricted Infrastructure Controller", docs_url=None, redoc_url=None)
_client = None


class StressRequest(BaseModel):
    kind: str = Field(pattern="^(cpu|memory)$")


def authorize(authorization: str | None):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "Controller authentication failed")


def container(name: str):
    if name not in ALLOWED:
        raise HTTPException(403, "Container is not in the demo allowlist")
    global _client
    if _client is None:
        try:
            import docker
            _client = docker.DockerClient(base_url=DOCKER_BASE_URL, timeout=10)
        except Exception as exc:
            raise HTTPException(503, f"Docker controller unavailable: {exc}") from exc
    try:
        return _client.containers.get(name)
    except Exception as exc:
        raise HTTPException(404, f"Allowlisted container unavailable: {name}") from exc


@app.get("/health")
def health():
    return {"status": "healthy", "controller": "restricted"}


@app.get("/containers/{name}/status")
def status(name: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    item = container(name)
    item.reload()
    return {"name": name, "status": item.status, "image": item.image.tags}


@app.post("/containers/{name}/start")
def start(name: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    item = container(name)
    item.start()
    item.reload()
    return {"name": name, "status": item.status, "action": "start"}


@app.post("/containers/{name}/stop")
def stop(name: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    item = container(name)
    item.stop(timeout=5)
    item.reload()
    return {"name": name, "status": item.status, "action": "stop"}


@app.post("/containers/{name}/restart")
def restart(name: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    item = container(name)
    item.reload()
    if item.status == "running":
        item.restart(timeout=10)
        action = "restart"
    else:
        item.start()
        action = "start"
    item.reload()
    return {"name": name, "status": item.status, "action": action}


@app.post("/stressors/{name}/run")
def run_stressor(name: str, payload: StressRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    expected = {"cpu-stressor": "cpu", "memory-stressor": "memory"}
    if expected.get(name) != payload.kind:
        raise HTTPException(403, "Stressor kind and target do not match the allowlist")
    item = container(name)
    result = item.exec_run(["python", "/app/stress.py", payload.kind, "--seconds", "45"], detach=True)
    return {"name": name, "kind": payload.kind, "exec_id": getattr(result, "id", None), "status": "started", "max_duration_seconds": 45}
