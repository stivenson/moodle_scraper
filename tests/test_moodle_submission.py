from pathlib import Path

import pytest

from lms_agent_scraper.tools.moodle_submission import (
    _remove_existing_submission_files,
    _upload_submission_files,
    read_assignment_details,
    validate_submission_action,
)

BASE_URL = "https://lms.example.edu"
ASSIGNMENT_URL = BASE_URL + "/mod/assign/view.php?id=42"


def test_submission_mutations_require_explicit_confirmation():
    with pytest.raises(ValueError, match="confirmación explícita"):
        validate_submission_action("create", ASSIGNMENT_URL, BASE_URL, "work.pdf", False)


def test_submission_actions_reject_urls_outside_the_configured_portal():
    with pytest.raises(ValueError, match="portal configurado"):
        validate_submission_action(
            "delete", "https://attacker.example/mod/assign/view.php?id=42", BASE_URL, None, True
        )


@pytest.mark.parametrize(
    "url",
    [
        BASE_URL + "/mod/assign/view.php?id=42&id=43",
        BASE_URL + "/mod/assign/view.php?id=",
        BASE_URL + "/mod/assign/view.php?id=abc",
    ],
)
def test_submission_actions_reject_ambiguous_or_non_numeric_activity_ids(url):
    with pytest.raises(ValueError, match="identificador"):
        validate_submission_action("read", url, BASE_URL, None, False)


def test_create_and_update_require_an_existing_file(tmp_path: Path):
    with pytest.raises(ValueError, match="archivo local existente"):
        validate_submission_action(
            "update", ASSIGNMENT_URL, BASE_URL, str(tmp_path / "missing.pdf"), True
        )


def test_create_accepts_three_existing_files_for_a_multi_file_assignment(tmp_path: Path):
    files = [tmp_path / "informe.pdf", tmp_path / "analisis.omv", tmp_path / "analisis.R"]
    for file in files:
        file.write_bytes(b"data")

    result = validate_submission_action(
        "create",
        ASSIGNMENT_URL,
        BASE_URL,
        None,
        True,
        file_paths=[str(file) for file in files],
    )

    assert result == [file.resolve() for file in files]


def test_submission_rejects_more_than_five_files(tmp_path: Path):
    files = [tmp_path / f"file-{index}.pdf" for index in range(6)]
    for file in files:
        file.write_bytes(b"pdf")

    with pytest.raises(ValueError, match="máximo de 5 archivos"):
        validate_submission_action(
            "create",
            ASSIGNMENT_URL,
            BASE_URL,
            None,
            True,
            file_paths=[str(file) for file in files],
        )


def test_submission_rejects_files_over_the_moodle_size_limit(tmp_path: Path):
    oversized = tmp_path / "too-large.pdf"
    oversized.write_bytes(b"x")
    oversized.write_bytes(b"x" * (20 * 1024 * 1024 + 1))

    with pytest.raises(ValueError, match="20 MB"):
        validate_submission_action("create", ASSIGNMENT_URL, BASE_URL, str(oversized), True)


def test_read_is_allowed_without_confirmation_and_mutations_are_supported():
    assert validate_submission_action("read", ASSIGNMENT_URL, BASE_URL, None, False) is None


def test_read_assignment_details_extracts_instructions_and_real_status():
    class Response:
        text = """
        <main id="region-main">
          <h1>Integral workshop</h1>
          <div class="activity-description"><p>Resuelve los ejercicios 1 a 4.</p>
            <a href="/pluginfile.php/2/guia.pdf">Guía</a></div>
          <table class="generaltable">
            <tr><th>Estado de la entrega</th><td>No entregada</td></tr>
          </table>
        </main>
        """

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            assert url == ASSIGNMENT_URL
            return Response()

    result = read_assignment_details(ASSIGNMENT_URL, Session())

    assert result["title"] == "Integral workshop"
    assert "ejercicios 1 a 4" in result["instructions"]
    assert result["submission_status"]["submitted"] is False
    assert result["attached_files"] == [{"name": "Guía", "url": "/pluginfile.php/2/guia.pdf"}]


def test_read_assignment_details_uses_moodle_page_header_outside_region_main():
    class Response:
        text = """
        <html><head><title>Curso: Final project report | Aula Pregrado</title></head>
        <body><header id="page-header"><h1>Final project report</h1></header>
        <div id="region-main"><div class="activity-description">
          <p>Entregue el informe final en PDF y el enlace de la aplicación.</p>
        </div><table class="generaltable"><tr><th>Estado de la entrega</th>
          <td>Todavía no se han realizado envíos</td></tr></table></div></body></html>
        """

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            return Response()

    result = read_assignment_details(ASSIGNMENT_URL, Session())

    assert result["title"] == "Final project report"
    assert "enlace de la aplicación" in result["instructions"]


def test_teacher_activity_attachment_is_not_reported_as_a_student_submission():
    class Response:
        text = """
        <html><body><h1>Proyecto Integrador - Parcial III</h1>
        <div class="activity-description">Entrega el informe final.
          <div class="fileuploadsubmission">
          <a href="/pluginfile.php/7/instrucciones.zip">
            Proyecto_Integrador_Parcial_Ciencia_de_Datos.zip</a>
        </div></div>
        <table class="submissionstatustable">
          <tr><th>Estado de la entrega</th><td>Enviado para calificar</td></tr>
          <tr><th>Archivos enviados</th><td><a>informe.pdf</a></td></tr>
        </table>
        </body></html>
        """

        def raise_for_status(self):
            pass

    class Session:
        def get(self, url, timeout):
            return Response()

    result = read_assignment_details(ASSIGNMENT_URL, Session())

    assert result["submission_status"]["state"] == "submitted"
    assert result["attached_files"] == [
        {
            "name": "Proyecto_Integrador_Parcial_Ciencia_de_Datos.zip",
            "url": "/pluginfile.php/7/instrucciones.zip",
        }
    ]
    assert result["submitted_files"] == ["informe.pdf"]


def test_submission_login_waits_for_username_field_before_filling(monkeypatch, tmp_path):
    import sys
    from types import ModuleType

    import pytest

    import lms_agent_scraper.tools.moodle_submission as submission

    pdf = tmp_path / "informe.pdf"
    pdf.write_bytes(b"pdf")
    events = []

    class FakeLocator:
        def all(self):
            return []

        def count(self):
            return 0

    class FakePage:
        def goto(self, url, **kwargs):
            events.append(("goto", url))

        def wait_for_selector(self, selector, **kwargs):
            events.append(("wait", selector))

        def fill(self, selector, value):
            events.append(("fill", selector))
            assert ("wait", selector) in events, "login field was filled before it appeared"

        def click(self, selector):
            events.append(("click", selector))

        def wait_for_load_state(self, state, **kwargs):
            events.append(("load", state))

        def content(self):
            return """<table><tr><th>Estado de la entrega</th>
            <td>Todavía no se han realizado envíos</td></tr></table>"""

        def locator(self, selector):
            return FakeLocator()

    page = FakePage()

    class FakeContext:
        def new_page(self):
            return page

    class FakeBrowser:
        def new_context(self, **kwargs):
            assert "user_agent" in kwargs
            return FakeContext()

        def close(self):
            pass

    class FakePlaywright:
        chromium = type(
            "FakeChromium", (), {"launch": staticmethod(lambda **kwargs: FakeBrowser())}
        )()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    fake_playwright = ModuleType("playwright")
    fake_sync_api = ModuleType("playwright.sync_api")
    fake_sync_api.TimeoutError = TimeoutError
    fake_sync_api.sync_playwright = lambda: FakePlaywright()
    monkeypatch.setitem(sys.modules, "playwright", fake_playwright)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync_api)

    with pytest.raises(RuntimeError, match="Moodle no mostró una acción disponible"):
        submission.manage_assignment_submission(
            action="create",
            assignment_url=ASSIGNMENT_URL,
            base_url=BASE_URL + "/login/index.php",
            username="student",
            password="secret",
            auth_profile={
                "login_path": "/login/index.php",
                "form_selectors": {
                    "username": "#username",
                    "password": "#password",
                    "submit": "#loginbtn",
                },
            },
            profile={},
            file_path=str(pdf),
            confirmed=True,
        )

    assert events[0] == ("goto", BASE_URL + "/login/index.php")
    assert events.index(("wait", "#username")) < events.index(("fill", "#username"))


def test_submission_files_use_moodles_native_file_picker(tmp_path):
    files = [tmp_path / "informe.pdf", tmp_path / "analisis.omv"]
    for file in files:
        file.write_bytes(b"data")
    events = []
    selected_name = {"value": "", "button": "Seleccionar este archivo"}

    class FileChooser:
        def set_files(self, path):
            events.append(("chooser_file", path))
            selected_name["value"] = Path(path).name

    class ExpectedFileChooser:
        value = FileChooser()

        def __enter__(self):
            events.append(("expect_file_chooser",))
            return self

        def __exit__(self, *args):
            pass

    class Locator:
        def __init__(self, selector, scope="page"):
            self.selector = selector
            self.scope = scope

        def count(self):
            if self.selector in {"Seleccionar", "Seleccionar este archivo"}:
                return int(self.selector == selected_name["button"])
            return 1

        @property
        def first(self):
            return self

        @property
        def last(self):
            return self

        def get_by_text(self, *args, **kwargs):
            return Locator(args[0], scope=self.selector)

        def locator(self, selector):
            return Locator(selector, scope=self.selector)

        def nth(self, index):
            return self

        def is_visible(self):
            if self.selector == "input[type='file'][name='repo_upload_file']":
                return False
            return True

        def click(self):
            if self.selector == "input[type='file'][name='repo_upload_file']":
                raise RuntimeError("Playwright cannot click a hidden file input")
            events.append(("click", self.scope, self.selector))

        def all(self):
            if self.selector == "Cargando...":
                return [Locator(self.selector, scope=self.scope) for _ in range(4)]
            return [self]

        def inner_text(self, timeout=None):
            return (
                "Subir este archivo"
                if self.selector == "button, input[type='submit'], a.btn"
                else ""
            )

        def get_attribute(self, name):
            return None

        def wait_for(self, **kwargs):
            if self.selector in {"Seleccionar", "Seleccionar este archivo"} and not self.count():
                raise TimeoutError("No está en el diálogo")
            events.append(("wait_for", self.scope, self.selector, kwargs.get("state")))

        def set_input_files(self, path):
            events.append(("set_file", self.scope, path))

        def evaluate(self, script):
            if "repo_upload_file" in self.selector:
                return [selected_name["value"]] if selected_name["value"] else []
            return None

    class Page:
        def locator(self, selector):
            return Locator(selector)

        def get_by_text(self, text, exact=False):
            return Locator(text)

        def expect_file_chooser(self, **kwargs):
            return ExpectedFileChooser()

    _upload_submission_files(Page(), files)

    uploads = [event for event in events if event[0] == "chooser_file"]
    assert uploads == [("chooser_file", str(file)) for file in files]
    assert [event for event in events if event[0] == "expect_file_chooser"] == [
        ("expect_file_chooser",),
        ("expect_file_chooser",),
    ]
    assert (
        "click",
        ".moodle-dialogue-wrap.yui3-widget-content-expanded",
        ".fp-file label",
    ) in events
    assert not any(
        event[0] == "click" and event[2] == "input[type='file'][name='repo_upload_file']"
        for event in events
    )
    assert (
        "click",
        ".moodle-dialogue-wrap.yui3-widget-content-expanded",
        "button, input[type='submit'], a.btn",
    ) in events
    for file in files:
        dialog_scope = ".moodle-dialogue-wrap.yui3-widget-content-expanded"
        assert ("wait_for", dialog_scope, file.name, "visible") in events
        select = ("click", dialog_scope, "Seleccionar este archivo")
        assert select in events
        assert (
            "wait_for",
            "[data-fieldtype='filemanager'] .filemanager.fm-loaded"
            ":not(.fm-loading):not(.fm-updating)",
            file.name,
            "visible",
        ) in events


def test_filemanager_waits_for_async_widget_insertion_and_loading_to_finish():
    from lms_agent_scraper.tools.moodle_submission import _wait_for_submission_filemanager

    widget_state = {"inserted": False, "ready": False}
    events = []
    modern = "[data-fieldtype='filemanager'] .filemanager:not(.fp-select)"
    ready = (
        "[data-fieldtype='filemanager'] .filemanager.fm-loaded:not(.fm-loading):not(.fm-updating)"
    )

    class Locator:
        def __init__(self, selector, parent="page"):
            self.selector, self.parent = selector, parent

        @property
        def first(self):
            return self

        def count(self):
            if self.selector == modern:
                return int(widget_state["inserted"])
            if self.selector == ready:
                return int(widget_state["ready"])
            return 1

        def all(self):
            return [self]

        def wait_for(self, *, state: str, timeout: int):
            events.append((self.selector, state))
            if self.selector == modern and state == "attached":
                assert not self.count(), "the widget should not exist before the wait"
                widget_state["inserted"] = True
            elif self.selector == ready and state == "visible":
                widget_state["ready"] = True

        def get_by_text(self, text, exact=False):
            result = Locator(text, self.selector)
            return result

    class Page:
        def locator(self, selector):
            result = Locator(selector)
            return result

    manager = _wait_for_submission_filemanager(Page())

    assert manager.selector == ready
    assert widget_state == {"inserted": True, "ready": True}
    assert events == [
        (modern, "attached"),
        (ready, "visible"),
    ]


def test_filepicker_accepts_moodle_theme_that_attaches_without_confirmation(monkeypatch, tmp_path):
    import lms_agent_scraper.tools.moodle_submission as submission

    artifact = tmp_path / "informe.pdf"
    artifact.write_bytes(b"pdf")
    events = []

    class FileChooser:
        def set_files(self, path):
            events.append(("set_files", path))

    class ChooserContext:
        value = FileChooser()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Locator:
        def __init__(self, selector, parent="page"):
            self.selector, self.parent = selector, parent

        @property
        def first(self):
            return self

        @property
        def last(self):
            return self

        def count(self):
            return 1

        def locator(self, selector):
            return Locator(selector, self.selector)

        def get_by_text(self, text, exact=False):
            return Locator(text, self.selector)

        def nth(self, index):
            return self

        def click(self):
            events.append(("click", self.parent, self.selector))

        def all(self):
            return [self]

        def wait_for(self, **kwargs):
            events.append(("wait_for", self.parent, self.selector, kwargs.get("state")))

        def inner_text(self, timeout=None):
            return (
                "Subir este archivo"
                if self.selector == "button, input[type='submit'], a.btn"
                else ""
            )

        def evaluate(self, script):
            return [artifact.name]

        def is_visible(self):
            return True

    class Page:
        def locator(self, selector):
            return Locator(selector)

        def get_by_text(self, text, exact=False):
            return Locator(text)

        def expect_file_chooser(self, **kwargs):
            return ChooserContext()

    monkeypatch.setattr(submission, "_wait_for_visible_text", lambda *_a, **_k: False)
    page = Page()

    submission._upload_submission_files(page, [artifact])

    assert ("set_files", str(artifact)) in events
    assert not any(event[0] == "click" and event[-1] == "Seleccionar" for event in events)
    assert (
        "wait_for",
        "[data-fieldtype='filemanager'] .filemanager.fm-loaded:not(.fm-loading):not(.fm-updating)",
        artifact.name,
        "visible",
    ) in events


def test_update_stops_when_moodle_delete_confirmation_is_not_available():
    class DeleteLocator:
        first = None

        def count(self):
            return 1

        def click(self):
            pass

    delete_locator = DeleteLocator()
    delete_locator.first = delete_locator

    class EmptyButtons:
        def all(self):
            return []

    class Page:
        def locator(self, selector):
            if selector == ".fp-file-delete":
                return delete_locator
            return EmptyButtons()

    with pytest.raises(RuntimeError, match="Moodle no mostró una acción disponible"):
        _remove_existing_submission_files(Page())


def test_update_accepts_an_existing_draft_but_create_does_not(tmp_path):
    draft = tmp_path / "informe.pdf"
    draft.write_bytes(b"data")

    result = validate_submission_action(
        "update",
        ASSIGNMENT_URL,
        BASE_URL,
        str(draft),
        True,
        submission_state="draft",
    )

    assert result == [draft.resolve()]
    with pytest.raises(ValueError, match="estado de entrega"):
        validate_submission_action(
            "create",
            ASSIGNMENT_URL,
            BASE_URL,
            str(draft),
            True,
            submission_state="draft",
        )


def test_direct_file_input_waits_until_every_uploaded_filename_is_visible(tmp_path):
    files = [tmp_path / "informe.pdf", tmp_path / "analisis.omv"]
    for file in files:
        file.write_bytes(b"data")
    events = []

    class Locator:
        def __init__(self, selector):
            self.selector = selector

        @property
        def first(self):
            return self

        def count(self):
            return 1 if self.selector == "input[type='file']:not([name='repo_upload_file'])" else 0

        def set_input_files(self, paths):
            events.append(("set_files", paths))

        def wait_for(self, **kwargs):
            events.append(("verify_name", self.selector, kwargs.get("state")))

    class Page:
        def locator(self, selector):
            return Locator(selector)

        def get_by_text(self, text, exact=False):
            return Locator(text)

    _upload_submission_files(Page(), files)

    set_event = next(event for event in events if event[0] == "set_files")
    assert set_event == ("set_files", [str(file) for file in files])
    verified = [
        event
        for event in events
        if event[0] == "verify_name" and event[1] in {f.name for f in files}
    ]
    assert [event[1] for event in verified] == [file.name for file in files]
    assert all(event[2] == "visible" for event in verified)


def test_update_is_not_verified_when_moodle_keeps_the_old_file(monkeypatch, tmp_path):
    import sys
    from types import ModuleType

    import lms_agent_scraper.tools.moodle_submission as submission

    replacement = tmp_path / "nuevo.pdf"
    replacement.write_bytes(b"pdf")

    class Locator:
        def __init__(self, page, selector, label=""):
            self.page, self.selector, self.label = page, selector, label

        @property
        def first(self):
            return self

        def count(self):
            if self.selector == ".fp-file-delete":
                return 0 if self.page.deleted_old else 1
            if self.selector == ".fp-btn-add a":
                return 0
            if self.selector == "input[type='file']:not([name='repo_upload_file'])":
                return 1
            return 0

        def click(self):
            if self.label == "Editar entrega":
                self.page.stage = "editing"
            elif self.label == "Eliminar":
                self.page.deleted_old = True
            elif self.label == "Guardar cambios":
                self.page.stage = "saved"
            elif self.label == "Enviar tarea":
                self.page.stage = "awaiting_confirmation"
            elif self.label == "Continuar":
                self.page.stage = "submitted"

        def inner_text(self, timeout=None):
            return self.label

        def get_attribute(self, name):
            return None

        def set_input_files(self, paths):
            self.page.uploaded = paths

        def wait_for(self, **kwargs):
            pass

        def all(self):
            return []

    class Page:
        def __init__(self):
            self.stage = "login"
            self.visited_assignment = False
            self.deleted_old = False
            self.uploaded = []

        def goto(self, url, **kwargs):
            if url == ASSIGNMENT_URL and not self.visited_assignment:
                self.stage = "before"
                self.visited_assignment = True

        def wait_for_selector(self, selector, **kwargs):
            pass

        def fill(self, selector, value):
            pass

        def click(self, selector):
            pass

        def wait_for_load_state(self, state, **kwargs):
            pass

        def locator(self, selector):
            if selector == "button, input[type='submit'], a.btn":
                labels = {
                    "before": ["Editar entrega"],
                    "editing": ["Eliminar", "Guardar cambios"],
                    "saved": ["Enviar tarea"],
                    "awaiting_confirmation": ["Continuar"],
                    "submitted": [],
                }.get(self.stage, [])
                return type(
                    "Buttons",
                    (),
                    {"all": lambda _: [Locator(self, selector, label) for label in labels]},
                )()
            return Locator(self, selector)

        def get_by_text(self, text, exact=False):
            return Locator(self, text)

        def content(self):
            if self.stage == "submitted":
                # Moodle still shows the previously submitted file, not the replacement.
                return """<table><tr><th>Estado de la entrega</th>
                <td>Enviado para calificar</td></tr>
                <tr><th>Archivos enviados</th><td><a>anterior.pdf</a></td></tr></table>"""
            if self.stage == "saved":
                return """<table><tr><th>Estado de la entrega</th>
                <td>Borrador (no enviado)</td></tr></table>"""
            return """<table><tr><th>Estado de la entrega</th>
            <td>Borrador (no enviado)</td></tr>
            <tr><th>Archivos enviados</th><td><a>anterior.pdf</a></td></tr></table>"""

    page = Page()

    class FakeContext:
        def new_page(self):
            return page

    class FakeBrowser:
        def new_context(self, **kwargs):
            return FakeContext()

        def close(self):
            pass

    class FakePlaywright:
        chromium = type("Chromium", (), {"launch": staticmethod(lambda **kwargs: FakeBrowser())})()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    fake_playwright = ModuleType("playwright")
    fake_sync_api = ModuleType("playwright.sync_api")
    fake_sync_api.TimeoutError = TimeoutError
    fake_sync_api.sync_playwright = lambda: FakePlaywright()
    monkeypatch.setitem(sys.modules, "playwright", fake_playwright)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", fake_sync_api)

    with pytest.raises(RuntimeError, match="no confirmó el envío de todos los archivos"):
        submission.manage_assignment_submission(
            action="update",
            assignment_url=ASSIGNMENT_URL,
            base_url=BASE_URL,
            username="student",
            password="secret",
            auth_profile={"login_path": "/login/"},
            profile={},
            file_path=str(replacement),
            confirmed=True,
        )
