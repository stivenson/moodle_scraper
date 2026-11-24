"""Tests para extracción de tareas desde HTML de página de curso (estilo Moodle)."""

from pathlib import Path

import pytest

from lms_agent_scraper.core.profile_loader import ProfileLoader
from lms_agent_scraper.tools.extraction_tools import (
    _course_section_pages,
    extract_assignments_from_html,
    get_assignments_for_courses,
    session_from_cookies,
)

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def _moodle_profile() -> dict:
    """Carga un perfil de ejemplo con selectores específicos para Unisimón."""
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
    # base_url de ejemplo (Unisimon).
    base_url = "https://lms.example.edu"
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
    assert assignment.get("submission_status", {}).get("submitted") is None
    assert assignment.get("submission_status", {}).get("status_text") == "Estado no verificado"


def test_extract_assignments_from_html_detects_quiz_with_due_date(moodle_profile):
    """
    En el mismo HTML hay un quiz con fecha; debe detectarse como tipo quiz.
    """
    # base_url de ejemplo (Unisimon).
    base_url = "https://lms.example.edu"
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


def test_extract_assignments_from_html_rejects_external_or_downgraded_activity_links(
    moodle_profile,
):
    base_url = "https://lms.example.edu"
    html = """
      <a href="/mod/assign/view.php?id=42">Tarea segura del curso</a>
      <a href="https://evil.example/mod/assign/view.php?id=43">Tarea externa</a>
      <a href="http://lms.example.edu/mod/assign/view.php?id=44">Tarea sin TLS</a>
      <a href="/mod/assign/view.php?id=45&amp;id=46">Tarea con id duplicado</a>
    """

    result = extract_assignments_from_html(
        html,
        course_name="Matemáticas I",
        course_url=f"{base_url}/course/view.php?id=1",
        profile=moodle_profile,
        base_url=base_url,
    )

    assert [item["url"] for item in result] == [f"{base_url}/mod/assign/view.php?id=42"]


def test_assignment_state_request_failure_returns_explicit_unknown_state():
    from lms_agent_scraper.tools.submission_tools import enrich_assignment_submission_status

    class Session:
        def get(self, *_args, **_kwargs):
            raise OSError("portal no disponible")

    result = enrich_assignment_submission_status(
        [
            {
                "type": "assignment",
                "title": "Tarea",
                "url": "https://example.test/mod/assign/view.php?id=1",
            }
        ],
        Session(),
    )

    assert result[0]["submission_status"]["submitted"] is None
    assert result[0]["submission_status"]["state"] == "unknown"


def test_get_assignments_for_courses_visits_all_linked_moodle_sections(monkeypatch, moodle_profile):
    from lms_agent_scraper.tools import extraction_tools

    base_url = "https://lms.example.edu"
    course_url = f"{base_url}/course/view.php?id=8100"
    pages = {
        course_url: """
          <a href="/course/view.php?id=8100&amp;section=0#tabs-tree-start">Unidad 1</a>
          <a href="/course/view.php?id=8100&amp;section=3#tabs-tree-start">Unidad 3</a>
        """,
        f"{base_url}/course/view.php?id=8100&section=0": """
          <li class="activity assign modtype_assign"><div class="activity-info">
            <a href="/mod/assign/view.php?id=9001">Unit 1 workshop</a>
            <span class="due-date">20/11/2026</span></div></li>
        """,
        f"{base_url}/course/view.php?id=8100&section=3": """
          <li class="activity assign modtype_assign"><div class="activity-info">
            <a href="/mod/assign/view.php?id=9002">Final project report</a>
            <span class="due-date">23/11/2026</span></div></li>
        """,
    }

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    class Session:
        calls = []

        def get(self, url, timeout):
            self.calls.append(url)
            return Response(pages[url])

    session = Session()
    monkeypatch.setattr(extraction_tools, "session_from_cookies", lambda *_: session)
    monkeypatch.setattr(
        extraction_tools,
        "enrich_assignment_submission_status",
        lambda items, *_args, **_kwargs: items,
    )
    monkeypatch.setattr(extraction_tools.time, "sleep", lambda *_: None)

    result = get_assignments_for_courses(
        courses=[{"url": course_url, "name": "Course A"}],
        cookies=[],
        profile=moodle_profile,
        base_url=base_url,
    )

    assert {item["url"].rsplit("=", 1)[-1] for item in result} == {"9001", "9002"}
    assert any("section=3" in url for url in session.calls)
    project = next(item for item in result if item["url"].endswith("id=9002"))
    assert project["section"] == "Unidad 3"


def test_course_section_links_require_same_scheme_course_id_and_single_values():
    base = "https://lms.example.edu/course/view.php?id=8100"
    html = """
      <a href="/course/view.php?id=8100&amp;section=3">Unidad 3</a>
      <a href="http://lms.example.edu/course/view.php?id=8100&amp;section=4">HTTP</a>
      <a href="/course/view.php?id=8100&amp;id=3820&amp;section=5">ID duplicado</a>
      <a href="/course/view.php?id=8100&amp;section=1&amp;section=6">Sección duplicada</a>
      <a href="/course/view.php?id=3820&amp;section=2">Otro curso</a>
    """

    pages = _course_section_pages(html, base)

    assert pages == [
        (base, "Main"),
        ("https://lms.example.edu/course/view.php?id=8100&section=3", "Unidad 3"),
    ]


def test_course_section_page_count_is_bounded():
    base = "https://lms.example.edu/course/view.php?id=8100"
    links = "".join(
        f'<a href="/course/view.php?id=8100&amp;section={i}">Unidad {i}</a>' for i in range(1, 27)
    )

    with pytest.raises(RuntimeError, match="límite de 25 secciones"):
        _course_section_pages(links, base)


def test_course_section_failure_marks_the_scrape_incomplete(monkeypatch, moodle_profile):
    from lms_agent_scraper.tools import extraction_tools

    base = "https://lms.example.edu"
    course_url = f"{base}/course/view.php?id=8100"

    class Response:
        text = '<a href="/course/view.php?id=8100&amp;section=3">Unidad 3</a>'

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            if "section=3" in url:
                raise OSError("sección no disponible")
            return Response()

    monkeypatch.setattr(extraction_tools, "session_from_cookies", lambda *_: Session())
    with pytest.raises(RuntimeError, match="resultado es incompleto"):
        get_assignments_for_courses(
            [{"url": course_url, "name": "Course A"}], [], moodle_profile, base
        )


def test_llm_assignment_results_are_revalidated_before_status_requests(monkeypatch, moodle_profile):
    from lms_agent_scraper.tools import extraction_tools

    base = "https://lms.example.edu"
    course_url = f"{base}/course/view.php?id=8100"

    class Response:
        text = "<html></html>"

        def raise_for_status(self):
            pass

    class Session:
        def get(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(extraction_tools, "session_from_cookies", lambda *_: Session())
    monkeypatch.setattr(
        extraction_tools,
        "extract_assignments_from_html_with_llm",
        lambda *_args, **_kwargs: [
            {
                "title": "Tarea externa",
                "type": "assignment",
                "url": "https://evil.example/mod/assign/view.php?id=1",
            }
        ],
    )

    with pytest.raises(RuntimeError, match="resultado es incompleto.*URL de actividad"):
        get_assignments_for_courses(
            [{"url": course_url, "name": "Course A"}],
            [],
            moodle_profile,
            base,
            use_llm_first=True,
        )


def test_llm_assignment_results_keep_their_course_section(monkeypatch, moodle_profile):
    from lms_agent_scraper.tools import extraction_tools

    base = "https://lms.example.edu"
    course_url = f"{base}/course/view.php?id=8100"
    section_url = f"{base}/course/view.php?id=8100&section=3"
    pages = {
        course_url: '<a href="/course/view.php?id=8100&amp;section=3">Unidad 3</a>',
        section_url: "<html></html>",
    }

    class Response:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, **_kwargs):
            return Response(pages[url])

    monkeypatch.setattr(extraction_tools, "session_from_cookies", lambda *_: Session())
    monkeypatch.setattr(
        extraction_tools,
        "extract_assignments_from_html_with_llm",
        lambda *_args, **_kwargs: [
            {
                "title": "Final project report",
                "type": "assignment",
                "url": f"{base}/mod/assign/view.php?id=9002",
                "section": "Main",
            }
        ],
    )
    monkeypatch.setattr(
        extraction_tools,
        "enrich_assignment_submission_status",
        lambda items, *_args, **_kwargs: items,
    )
    monkeypatch.setattr(extraction_tools.time, "sleep", lambda *_: None)

    result = get_assignments_for_courses(
        [{"url": course_url, "name": "Course A"}],
        [],
        moodle_profile,
        base,
        use_llm_first=True,
    )

    assert result[0]["section"] == "Unidad 3"


def test_session_preserves_secure_cookie_attribute():
    session = session_from_cookies(
        [{"name": "MoodleSession", "value": "opaque", "domain": "lms.example.edu", "secure": True}],
        "https://lms.example.edu",
    )

    cookie = next(cookie for cookie in session.cookies if cookie.name == "MoodleSession")
    assert cookie.secure is True
