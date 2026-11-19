import pytest
from app.simulator.controller import DockerController, ControllerError


def test_controller_rejects_non_allowlisted_container_before_http(monkeypatch):
    controller = DockerController()
    with pytest.raises(ControllerError, match="not in the demo allowlist"):
        controller.status("production-database")


def test_stressor_action_is_fixed_allowlist(monkeypatch):
    controller = DockerController()
    with pytest.raises(ControllerError, match="not allowlisted"):
        controller.run_stressor("demo-postgres", "sh -c rm -rf /")
