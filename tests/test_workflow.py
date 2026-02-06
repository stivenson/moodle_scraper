"""Tests para el grafo LangGraph y workflow."""
from pathlib import Path

import pytest

from lms_agent_scraper.graph.state import ScraperState
from lms_agent_scraper.graph.workflow import build_workflow, run_workflow
from lms_agent_scraper.graph import nodes

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def test_build_workflow():
    graph = build_workflow()
    assert graph is not None


def test_run_workflow_stub_no_credentials():
    # Sin credenciales reales: debe cargar perfil y fallar auth o devolver estado coherente
    result = run_workflow(
        profile_name="moodle_default",
        base_url="https://example.edu",
        username="",
        password="",
        days_ahead=7,
        days_behind=7,
        max_courses=0,
        output_dir="reports",
        profiles_dir=PROFILES_DIR,
        debug=False,
    )
    assert "authenticated" in result
    assert "courses" in result
    assert "assignments" in result
    assert "report_path" in result
    assert result["authenticated"] is False
    assert isinstance(result.get("errors"), list)


def test_authentication_node_no_credentials():
    state: ScraperState = {
        "profile": {"auth": {"form_selectors": {}, "login_path": "/login/"}},
        "base_url": "https://example.edu",
        "username": "",
        "password": "",
        "errors": [],
    }
    out = nodes.authentication_node(state)
    assert out["authenticated"] is False
    assert out["session_cookies"] == []


def test_course_discovery_node_not_authenticated():
    state: ScraperState = {
        "authenticated": False,
        "session_cookies": [],
        "errors": [],
    }
    out = nodes.course_discovery_node(state)
    assert out["courses"] == []
