"""Tests para el servidor MCP (herramientas disponibles y list_profiles)."""

from pathlib import Path


# Importar después de conftest que añade src al path
from lms_agent_scraper.mcp import server
from lms_agent_scraper.mcp.server import list_profiles

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def test_list_profiles_tool_returns_string():
    # list_profiles es una herramienta MCP; al llamarla debe devolver string
    result = list_profiles()
    assert isinstance(result, str)
    # Si existe el directorio profiles con moodle_default, debe aparecer
    if PROFILES_DIR.exists():
        assert "moodle_default" in result or "No hay" in result


def test_full_workflow_surfaces_incomplete_extraction_errors(monkeypatch):
    class Portal:
        profile = "moodle_unisimon"
        base_url = "https://lms.example.edu"
        username = "student"
        password = "opaque"

    class Scraper:
        days_ahead = 60
        days_behind = 120
        max_courses = 0

    class Output:
        dir = Path("/tmp/reports")

    monkeypatch.setattr(server, "PortalSettings", Portal)
    monkeypatch.setattr(server, "ScraperSettings", Scraper)
    monkeypatch.setattr(server, "OutputSettings", Output)
    monkeypatch.setattr(server, "_profiles_dir", lambda: Path("/tmp/profiles"))
    monkeypatch.setattr(
        server,
        "run_workflow",
        lambda **_: {"assignments": [], "errors": ["El resultado es incompleto: falta Unidad 3"]},
    )

    result = server._run_full_workflow()

    assert "error" in result
    assert "resultado es incompleto" in result["error"]


def test_full_workflow_does_not_hide_unverified_submission_states(monkeypatch):
    class Portal:
        profile = "moodle_unisimon"
        base_url = "https://lms.example.edu"
        username = "student"
        password = "opaque"

    class Scraper:
        days_ahead = 60
        days_behind = 120
        max_courses = 0

    class Output:
        dir = Path("/tmp/reports")

    monkeypatch.setattr(server, "PortalSettings", Portal)
    monkeypatch.setattr(server, "ScraperSettings", Scraper)
    monkeypatch.setattr(server, "OutputSettings", Output)
    monkeypatch.setattr(server, "_profiles_dir", lambda: Path("/tmp/profiles"))
    monkeypatch.setattr(
        server,
        "run_workflow",
        lambda **_: {
            "assignments": [
                {
                    "type": "assignment",
                    "title": "Proyecto pendiente",
                    "submission_status": {"state": "unknown"},
                }
            ],
            "errors": [],
        },
    )

    result = server._run_full_workflow()

    assert "error" in result
    assert "no se pudo confirmar el estado" in result["error"]


def test_full_workflow_rejects_empty_course_discovery(monkeypatch):
    class Portal:
        profile = "moodle_unisimon"
        base_url = "https://lms.example.edu"
        username = "student"
        password = "opaque"

    class Scraper:
        days_ahead = 60
        days_behind = 120
        max_courses = 0

    class Output:
        dir = Path("/tmp/reports")

    monkeypatch.setattr(server, "PortalSettings", Portal)
    monkeypatch.setattr(server, "ScraperSettings", Scraper)
    monkeypatch.setattr(server, "OutputSettings", Output)
    monkeypatch.setattr(server, "_profiles_dir", lambda: Path("/tmp/profiles"))
    monkeypatch.setattr(
        server,
        "run_workflow",
        lambda **_: {"authenticated": True, "courses": [], "assignments": [], "errors": []},
    )

    result = server._run_full_workflow()

    assert "error" in result
    assert "no devolvió cursos" in result["error"]


def test_pending_assignments_rejects_missing_requested_course(monkeypatch):
    monkeypatch.setattr(
        server,
        "_run_full_workflow",
        lambda: {
            "authenticated": True,
            "courses": [{"name": "LMS Course A - 2797"}],
            "assignments": [],
            "errors": [],
        },
    )

    result = server.get_pending_assignments(course_names="Course A,Course B")

    assert "Scraper incompleto" in result
    assert "Course B" in result


def test_pending_assignments_rejects_a_requested_course_excluded_by_max_courses(monkeypatch):
    class Scraper:
        max_courses = 2
        target_courses = "Course A,Course B"

    monkeypatch.setattr(server, "ScraperSettings", Scraper)
    monkeypatch.setattr(
        server,
        "_run_full_workflow",
        lambda: {
            "authenticated": True,
            "courses": [
                {"name": "English"},
                {"name": "LMS Course A - 2797"},
                {"name": "LMS Course B DESCRIPTIVA Y PROBABILIDAD - 2799"},
            ],
            "assignments": [],
            "errors": [],
        },
    )

    result = server.get_pending_assignments(course_names="Course A,Course B")

    assert "Scraper incompleto" in result
    assert "Course B" in result


def test_pending_assignments_uses_configured_courses_instead_of_fixed_subjects(monkeypatch):
    class Scraper:
        max_courses = 0
        target_courses = "Biología,Historia"

    monkeypatch.setattr(server, "ScraperSettings", Scraper)
    monkeypatch.setattr(
        server,
        "_run_full_workflow",
        lambda: {
            "authenticated": True,
            "courses": [{"name": "Biología"}, {"name": "Historia"}],
            "assignments": [
                {
                    "title": "Informe de campo",
                    "course": "Biología",
                    "due_date": "24/11/2026",
                    "url": "https://lms.example/mod/assign/view.php?id=42",
                    "submission_status": {"submitted": False},
                }
            ],
            "errors": [],
        },
    )

    result = server.get_pending_assignments(days_ahead=7, days_behind=7)

    assert "Informe de campo" in result
    assert "Biología" in result


def test_target_assignment_scope_accepts_any_currently_discovered_course():
    result = {
        "assignments": [
            {
                "type": "assignment",
                "course": "Biología",
                "url": "https://lms.example/mod/assign/view.php?id=42",
            }
        ]
    }

    assert server._find_target_assignment(
        result, "https://lms.example/mod/assign/view.php?id=42"
    ) == result["assignments"][0]


def test_pending_assignments_without_course_filter_includes_all_discovered_courses(monkeypatch):
    class Scraper:
        max_courses = 0
        target_courses = ""

    monkeypatch.setattr(server, "ScraperSettings", Scraper)
    monkeypatch.setattr(
        server,
        "_run_full_workflow",
        lambda: {
            "authenticated": True,
            "courses": [{"name": "Biología"}, {"name": "Historia"}],
            "assignments": [
                {
                    "title": "Informe histórico",
                    "course": "Historia",
                    "due_date": "24/11/2026",
                    "url": "https://lms.example/mod/assign/view.php?id=43",
                    "submission_status": {"submitted": False},
                }
            ],
            "errors": [],
        },
    )

    result = server.get_pending_assignments(days_ahead=7, days_behind=7)

    assert "Informe histórico" in result
