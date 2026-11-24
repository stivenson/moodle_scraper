from datetime import date

from lms_agent_scraper.tools.submission_tools import (
    enrich_assignment_submission_status,
    filter_pending_assignments,
    parse_submission_status,
    _parse_relative_due_time,
)


def test_parse_submission_status_reads_moodle_assignment_status():
    html = """
    <table class="generaltable">
      <tr><th>Estado de la entrega</th><td>Enviado para calificar</td></tr>
      <tr><th>Estado de la calificación</th><td>Sin calificar</td></tr>
    </table>
    """

    assert parse_submission_status(html) == {
        "submitted": True,
        "state": "submitted",
        "status_text": "Enviado para calificar",
    }


def test_parse_submission_status_leaves_unrecognized_pages_unknown():
    assert parse_submission_status("<main>La actividad está disponible</main>") == {
        "submitted": None,
        "state": "unknown",
        "status_text": "Estado de entrega no identificado",
    }


def test_parse_submission_status_distinguishes_an_unsubmitted_draft():
    html = """<table><tr><th>Estado de la entrega</th>
    <td>Borrador (no enviado)</td></tr></table>"""

    status = parse_submission_status(html)

    assert status["submitted"] is False
    assert status["state"] == "draft"


def test_parse_submission_status_prioritizes_submission_over_pending_grade():
    html = """<table><tr><th>Estado de la entrega</th>
    <td>Enviado para calificar; pendiente de calificación</td></tr></table>"""

    status = parse_submission_status(html)

    assert status["submitted"] is True
    assert status["state"] == "submitted"


def test_parse_submission_status_ignores_mentions_outside_the_status_row():
    html = """
    <main><p>Recuerda completar la actividad no entregada antes de iniciar.</p>
    <table class="generaltable"><tr><th>Fecha de entrega</th><td>24/11/2026</td></tr></table>
    </main>
    """

    assert parse_submission_status(html)["submitted"] is None


def test_filter_pending_assignments_keeps_only_target_courses_and_unsubmitted():
    assignments = [
        {
            "title": "Taller 1",
            "course": "Course A 2026-2",
            "due_date": "25/11/2026",
            "submission_status": {"submitted": False},
        },
        {
            "title": "Quiz",
            "course": "Course B",
            "due_date": "20/11/2026",
            "submission_status": {"submitted": True},
        },
        {
            "title": "Parcial 1",
            "course": "Course B",
            "due_date": "19/11/2026",
            "submission_status": {"submitted": False},
        },
        {
            "title": "Lectura",
            "course": "Física",
            "due_date": "24/11/2026",
            "submission_status": {"submitted": False},
        },
        {
            "title": "Desconocida",
            "course": "Course B",
            "due_date": "24/11/2026",
            "submission_status": {"submitted": None},
        },
    ]

    pending = filter_pending_assignments(
        assignments,
        course_names=["Course A", "Course B"],
        today=date(2026, 11, 22),
        days_ahead=7,
        days_behind=7,
    )

    assert [item["title"] for item in pending] == ["Taller 1", "Parcial 1"]
    assert [item["status"] for item in pending] == ["UPCOMING", "OVERDUE"]


def test_filter_pending_assignments_with_no_course_filter_includes_any_course():
    pending = filter_pending_assignments(
        [
            {
                "title": "Lab report",
                "course": "Biology",
                "due_date": "25/11/2026",
                "submission_status": {"submitted": False},
            }
        ],
        course_names=[],
        today=date(2026, 11, 22),
    )

    assert [item["title"] for item in pending] == ["Lab report"]


def test_enrich_assignment_status_uses_detail_page_and_keeps_non_assignment_unknown():
    class Response:
        text = "<table><tr><th>Submission status</th><td>Submitted for grading</td></tr></table>"

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            assert url.endswith("id=12")
            return Response()

    result = enrich_assignment_submission_status(
        [
            {"type": "assignment", "url": "https://lms.example/mod/assign/view.php?id=12"},
            {"type": "quiz", "url": "https://lms.example/mod/quiz/view.php?id=13"},
        ],
        Session(),
    )

    assert result[0]["submission_status"]["submitted"] is True
    assert result[1]["submission_status"]["submitted"] is None


def test_enrich_assignment_uses_moodle_spanish_status_and_detail_due_date():
    class Response:
        text = """
        <main id="region-main">
          <table class="generaltable">
            <tr><th>Estado de la entrega</th><td>Todavía no se han realizado envíos</td></tr>
          </table>
          <div id="dates">Apertura: sábado, 21 de noviembre de 2026, 08:00
          Cierre: jueves, 26 de noviembre de 2026, 23:59</div>
        </main>
        """

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            return Response()

    profile = {
        "submission": {
            "indicators": {
                "submitted": ["enviado para calificar"],
                "pending": ["todavía no se han realizado envíos"],
            }
        },
        "dates": {"patterns": [r"(\d{1,2} de \w+ de \d{4})"]},
    }
    assignments = [{"type": "assignment", "url": "https://lms.example/mod/assign/view.php?id=9"}]

    result = enrich_assignment_submission_status(assignments, Session(), profile)

    assert result[0]["submission_status"]["submitted"] is False
    assert result[0]["due_date"] == "26 de noviembre de 2026"


def test_read_assignment_details_lists_only_files_in_submission_row():
    from lms_agent_scraper.tools.moodle_submission import read_assignment_details

    class Response:
        text = """<main id="region-main"><h1>Proyecto</h1>
        <table class="generaltable">
          <tr><th>Estado de la entrega</th><td>Enviado para calificar</td></tr>
          <tr><th>Archivos enviados</th><td><a href="/pluginfile.php/1/informe.pdf">informe.pdf</a>
          <a href="/pluginfile.php/1/analisis.omv">analisis.omv</a></td></tr>
          <tr><th>Archivos de ejemplo</th><td><a href="/pluginfile.php/1/guia.pdf">guia.pdf</a></td></tr>
        </table></main>"""

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            return Response()

    details = read_assignment_details(
        "https://lms.example/mod/assign/view.php?id=42", Session()
    )

    assert details["submitted_files"] == ["informe.pdf", "analisis.omv"]


def test_moodle_relative_countdown_is_kept_without_inventing_absolute_date():
    future = _parse_relative_due_time("Tiempo restante 1 día 8 horas restante")
    overdue = _parse_relative_due_time(
        "Tiempo restante La Tarea está retrasada por: 32 días 15 horas"
    )

    assert future == {
        "due_relative": "1 día 8 horas restante",
        "relative_status": "UPCOMING",
        "relative_hours": 32,
    }
    assert _parse_relative_due_time("Time remaining 1 day 8 hours") == {
        "due_relative": "1 day 8 hours",
        "relative_status": "UPCOMING",
        "relative_hours": 32,
    }
    assert overdue == {
        "due_relative": "La Tarea está retrasada por: 32 días 15 horas",
        "relative_status": "OVERDUE",
        "relative_hours": 783,
    }


def test_enrich_and_filter_classify_relative_moodle_timer_without_absolute_date():
    class Response:
        text = """
        <table><tr><th>Estado de la entrega</th>
        <td>Todavía no se han realizado envíos</td></tr></table>
        <p>Tiempo restante</p><p>La Tarea está retrasada por: 8 días 15 horas</p>
        """

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            return Response()

    assignment = {
        "type": "assignment",
        "url": "https://lms.example/mod/assign/view.php?id=10",
        "course": "LMS Course A",
        "title": "Guía 7",
    }
    enriched = enrich_assignment_submission_status([assignment], Session())[0]
    pending = filter_pending_assignments(
        [enriched], ["Course A"], today=date(2026, 11, 22), days_behind=120
    )

    assert enriched.get("due_date", "") == ""
    assert enriched["due_relative"] == "La Tarea está retrasada por: 8 días 15 horas"
    assert enriched["relative_status"] == "OVERDUE"
    assert enriched["relative_hours"] == 207
    assert len(pending) == 1
    assert pending[0]["status"] == "OVERDUE"
