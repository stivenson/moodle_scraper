"""Tests para extracción de tareas desde HTML de página de curso (estilo Moodle)."""

from pathlib import Path

import pytest

from lms_agent_scraper.core.profile_loader import ProfileLoader
from lms_agent_scraper.tools.extraction_tools import extract_assignments_from_html


PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def _moodle_profile() -> dict:
    """Carga perfil Moodle Unisimon como dict para los selectores."""
    loader = ProfileLoader(PROFILES_DIR)
    profile = loader.load("moodle_unisimon")
    return profile.model_dump()


@pytest.fixture
def moodle_profile():
    return _moodle_profile()


# HTML simulado: página de curso Moodle con una tarea (assign) con fecha de entrega próxima
# y un quiz con fecha, estilo bloque de actividad.
MOODLE_COURSE_PAGE_WITH_ASSIGNMENT = """
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><title>Curso - Matemáticas I</title></head>
<body>
<div id="region-main" class="col-12">
  <ul class="topics">
    <li class="section main" data-region="section">
      <div class="content">
        <ul class="section img-text">
          <li class="activity assign modtype_assign" data-region="activity-item">
            <div class="activity-info">
              <a href="/mod/assign/view.php?id=42" class="aalink">
                Tarea 1 - Entregar informe
              </a>
              <span class="due-date">15/03/2026</span>
            </div>
          </li>
          <li class="activity quiz modtype_quiz" data-region="activity-item">
            <div class="activity-info">
              <a href="/mod/quiz/view.php?id=88" class="aalink">Quiz parcial</a>
              <span class="due-date">20/03/2026</span>
            </div>
          </li>
        </ul>
      </div>
    </li>
  </ul>
</div>
</body>
</html>
"""


def test_extract_assignments_from_html_detects_assignment_with_due_date(moodle_profile):
    """
    Dado HTML de una página de curso Moodle con una tarea (mod/assign) y fecha de entrega,
    se detecta al menos una tarea con título, url, type y due_date correctos.
    """
    base_url = "https://aulapregrado.unisimon.edu.co"
    course_name = "Matemáticas I"
    course_url = f"{base_url}/course/view.php?id=1"

    result = extract_assignments_from_html(
        html=MOODLE_COURSE_PAGE_WITH_ASSIGNMENT,
        course_name=course_name,
        course_url=course_url,
        profile=moodle_profile,
        section_name="Main",
        base_url=base_url,
    )

    assert len(result) >= 1, "Debe detectarse al menos una tarea (assignment)"
    assignment = next((a for a in result if a["type"] == "assignment"), result[0])
    assert assignment["title"] == "Tarea 1 - Entregar informe"
    assert "mod/assign" in assignment["url"]
    assert assignment["course"] == course_name
    assert assignment["type"] == "assignment"
    assert assignment["due_date"] == "15/03/2026"
    assert assignment["section"] == "Main"
    assert assignment.get("submission_status") is not None
    assert assignment.get("submission_status", {}).get("status_text") == "No entregada"


def test_extract_assignments_from_html_detects_quiz_with_due_date(moodle_profile):
    """
    En el mismo HTML hay un quiz con fecha; debe detectarse como tipo quiz.
    """
    base_url = "https://aulapregrado.unisimon.edu.co"
    result = extract_assignments_from_html(
        html=MOODLE_COURSE_PAGE_WITH_ASSIGNMENT,
        course_name="Matemáticas I",
        course_url=f"{base_url}/course/view.php?id=1",
        profile=moodle_profile,
        base_url=base_url,
    )

    quiz = next((a for a in result if a["type"] == "quiz"), None)
    assert quiz is not None
    assert quiz["title"] == "Quiz parcial"
    assert "mod/quiz" in quiz["url"]
    assert quiz["due_date"] == "20/03/2026"


def test_extract_assignments_from_html_empty_returns_empty_list(moodle_profile):
    """HTML sin enlaces de tareas devuelve lista vacía."""
    html = """
    <html><body>
      <div class="content"><p>No hay actividades en este curso.</p></div>
    </body></html>
    """
    result = extract_assignments_from_html(
        html=html,
        course_name="Curso vacío",
        course_url="https://example.edu/course/1",
        profile=moodle_profile,
        base_url="https://example.edu",
    )
    assert result == []
