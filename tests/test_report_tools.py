"""Tests para report_tools."""
from datetime import datetime, timedelta

import pytest

from lms_agent_scraper.tools.report_tools import filter_by_date, generate_markdown_report, save_report


def test_filter_by_date_empty():
    assert filter_by_date([], 7, 7) == []


def test_filter_by_date_upcoming():
    today = datetime.now().date()
    future = (today + timedelta(days=3)).strftime("%Y-%m-%d")
    assignments = [{"due_date": future, "title": "Tarea", "course": "C1"}]
    filtered = filter_by_date(assignments, days_ahead=7, days_behind=0)
    assert len(filtered) == 1
    assert filtered[0]["status"] == "UPCOMING"
    assert filtered[0]["days_until_due"] == 3


def test_filter_by_date_overdue():
    today = datetime.now().date()
    past = (today - timedelta(days=2)).strftime("%Y-%m-%d")
    assignments = [{"due_date": past, "title": "Tarea", "course": "C1"}]
    filtered = filter_by_date(assignments, days_ahead=0, days_behind=7)
    assert len(filtered) == 1
    assert filtered[0]["status"] == "OVERDUE"
    assert filtered[0]["days_overdue"] == 2


def test_generate_markdown_report_empty():
    content = generate_markdown_report([], 7, 7, title="Test")
    assert "Reporte" in content or "Test" in content
    assert "generación" in content.lower() or "generado" in content.lower()
    assert "**Total tareas:** 0" in content
    assert "Sin tareas pendientes" in content


def test_generate_markdown_report_assignments_outside_period():
    """Con tareas fuera del período, el reporte debe mostrar Total tareas: 0 y mensaje sin tareas."""
    today = datetime.now().date()
    far_future = (today + timedelta(days=100)).strftime("%Y-%m-%d")
    assignments = [
        {"due_date": far_future, "title": "Tarea lejana", "course": "C1"},
    ]
    content = generate_markdown_report(
        assignments, days_ahead=21, days_behind=7, title="Test"
    )
    assert "**Total tareas:** 0" in content
    assert "Sin tareas pendientes" in content


def test_save_report(tmp_path):
    content = "# Test\n\nReporte de prueba."
    path = save_report(content, output_dir=str(tmp_path), prefix="test")
    assert path.endswith(".md")
    from pathlib import Path
    assert Path(path).exists()
    assert "test_" in Path(path).name
