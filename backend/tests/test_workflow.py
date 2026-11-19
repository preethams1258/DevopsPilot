import pytest
from app.agents.workflow import grounded_rule_analysis


def test_unknown_incident_does_not_recommend_action():
    state = {"title": "Something is wrong", "description": "Unknown failure", "findings": []}
    result = grounded_rule_analysis(state)
    assert result["remediation"]["action_type"] == "none"
    assert result["confidence"] < 0.5


def test_database_incident_proposes_demo_database_only():
    state = {"title": "Database failure", "description": "Postgres unavailable", "findings": []}
    result = grounded_rule_analysis(state)
    assert result["remediation"]["target"] == "demo-postgres"
    assert result["remediation"]["action_type"] == "start_container"
