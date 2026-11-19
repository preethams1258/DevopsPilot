"""Allowlisted Docker controller. Never accepts arbitrary commands or container IDs."""
from __future__ import annotations
import time
from app.core.config import settings


class ControllerError(RuntimeError):
    pass


class DockerController:
    """HTTP adapter to the isolated infrastructure controller; API never sees Docker socket."""

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        import httpx
        from app.core.config import settings
        try:
            response = httpx.request(method, f"{settings.controller_url}{path}", json=payload, headers={"Authorization": f"Bearer {settings.controller_token}"}, timeout=12)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise ControllerError(f"Infrastructure controller request failed: {exc}") from exc

    def status(self, name: str) -> dict:
        if name not in settings.allowed_containers:
            raise ControllerError(f"Container '{name}' is not in the demo allowlist")
        return self._request("GET", f"/containers/{name}/status")

    def restart(self, name: str) -> dict:
        if name not in settings.allowed_containers:
            raise ControllerError(f"Container '{name}' is not in the demo allowlist")
        return self._request("POST", f"/containers/{name}/restart")

    def stop(self, name: str) -> dict:
        if name not in settings.allowed_containers:
            raise ControllerError(f"Container '{name}' is not in the demo allowlist")
        return self._request("POST", f"/containers/{name}/stop")

    def start(self, name: str) -> dict:
        if name not in settings.allowed_containers:
            raise ControllerError(f"Container '{name}' is not in the demo allowlist")
        return self._request("POST", f"/containers/{name}/start")

    def run_stressor(self, name: str, kind: str) -> dict:
        expected = {"cpu-stressor": "cpu", "memory-stressor": "memory"}
        if expected.get(name) != kind or name not in settings.allowed_containers:
            raise ControllerError("Stressor action is not allowlisted")
        return self._request("POST", f"/stressors/{name}/run", {"kind": kind})

    def logs(self, name: str, tail: int = 100) -> str:
        raise ControllerError("Container logs are retrieved through Loki, not Docker API")


controller = DockerController()


class IncidentSimulator:
    SCENARIOS = [
        {"id": "database_failure", "name": "Database failure", "severity": "critical", "description": "Stops only the disposable demo PostgreSQL container."},
        {"id": "api_latency", "name": "API latency", "severity": "warning", "description": "Enables a bounded delay in the demo API."},
        {"id": "cpu_pressure", "name": "CPU pressure", "severity": "warning", "description": "Starts a resource-limited CPU stressor container."},
        {"id": "memory_pressure", "name": "Memory pressure", "severity": "warning", "description": "Starts a memory-limited stressor container."},
        {"id": "faulty_deployment", "name": "Faulty deployment", "severity": "critical", "description": "Switches the demo API into a controlled failing mode."},
    ]

    def inject(self, scenario: str) -> dict:
        if scenario == "database_failure":
            return controller.stop("demo-postgres")
        if scenario == "cpu_pressure":
            return controller.run_stressor("cpu-stressor", "cpu")
        if scenario == "memory_pressure":
            return controller.run_stressor("memory-stressor", "memory")
        if scenario in {"api_latency", "faulty_deployment"}:
            import httpx
            from app.core.config import settings
            mode = "latency" if scenario == "api_latency" else "faulty"
            response = httpx.post(f"{settings.monitored_api_url}/demo/fault", json={"mode": mode}, timeout=5)
            response.raise_for_status()
            return {"scenario": scenario, "result": response.json()}
        raise ControllerError("Unknown simulator scenario")

    def recover(self, scenario: str) -> dict:
        if scenario == "database_failure":
            return controller.start("demo-postgres")
        if scenario == "cpu_pressure":
            return {"status": "workload bounded to 45 seconds; container resource limits enforce safety"}
        if scenario == "memory_pressure":
            return {"status": "workload bounded to 45 seconds; container resource limits enforce safety"}
        if scenario in {"api_latency", "faulty_deployment"}:
            import httpx
            from app.core.config import settings
            response = httpx.post(f"{settings.monitored_api_url}/demo/fault", json={"mode": "normal"}, timeout=5)
            response.raise_for_status()
            return {"scenario": scenario, "result": response.json()}
        raise ControllerError("Unknown simulator scenario")


simulator = IncidentSimulator()
