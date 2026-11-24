"""Lectura y gestión acotada de entregas propias en Moodle."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from lms_agent_scraper.tools.submission_tools import parse_submission_status

SUPPORTED_ACTIONS = {"read", "create", "update", "delete"}
MAX_SUBMISSION_FILES = 5
MAX_SUBMISSION_FILE_SIZE = 20 * 1024 * 1024


def validate_submission_action(
    action: str,
    assignment_url: str,
    base_url: str,
    file_path: Optional[str],
    confirmed: bool,
    file_paths: Optional[Sequence[str]] = None,
    submission_state: Optional[str] = None,
) -> Optional[List[Path]]:
    """Valida alcance, archivo y confirmación antes de operar sobre Moodle."""
    if action not in SUPPORTED_ACTIONS:
        raise ValueError(f"Acción no soportada: {action}")
    target = urlparse(assignment_url)
    origin = urlparse(base_url)
    activity_ids = parse_qs(target.query, keep_blank_values=True).get("id", [])
    if (
        not target.scheme.startswith("http")
        or target.scheme.casefold() != origin.scheme.casefold()
        or target.netloc.casefold() != origin.netloc.casefold()
        or target.username
        or target.password
        or target.path.rstrip("/") != "/mod/assign/view.php"
    ):
        raise ValueError("La URL debe ser una actividad de entrega del portal configurado")
    if len(activity_ids) != 1 or not activity_ids[0].isdigit():
        raise ValueError("La actividad debe tener un identificador numérico único")
    if action == "read":
        return None
    if not confirmed:
        raise ValueError("Se requiere confirmación explícita para cambiar una entrega")
    if submission_state is not None:
        allowed_states = {
            "create": {"not_submitted"},
            "update": {"draft", "submitted"},
            "delete": {"draft", "submitted"},
        }
        if submission_state not in allowed_states[action]:
            raise ValueError(
                f"La acción {action} no corresponde al estado de entrega {submission_state}"
            )
    if action in {"create", "update"}:
        if file_path and file_paths:
            raise ValueError("Usa file_path o file_paths, no ambos")
        raw_paths = (
            list(file_paths) if file_paths is not None else ([file_path] if file_path else [])
        )
        if not raw_paths:
            raise ValueError("La acción requiere un archivo local existente")
        if len(raw_paths) > MAX_SUBMISSION_FILES:
            raise ValueError(f"La entrega admite un máximo de {MAX_SUBMISSION_FILES} archivos")
        candidates = [Path(path).expanduser().resolve() for path in raw_paths]
        if any(not candidate.is_file() for candidate in candidates):
            raise ValueError("La acción requiere un archivo local existente para cada adjunto")
        if any(candidate.stat().st_size > MAX_SUBMISSION_FILE_SIZE for candidate in candidates):
            raise ValueError("Cada archivo debe pesar como máximo 20 MB")
        return candidates
    return None


def read_assignment_details(
    assignment_url: str,
    session: Any,
    profile: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Lee instrucciones visibles, archivos y estado de la página de una entrega."""
    response = session.get(assignment_url, timeout=timeout)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    main = soup.select_one("#region-main") or soup.body or soup
    title_node = main.select_one("h1, h2") or soup.select_one("#page-header h1, header h1, h1")
    description = main.select_one(".activity-description, .intro, .box.generalbox")
    files = []
    for link in (description or main).select("a[href]"):
        href = link.get("href", "")
        label = link.get_text(" ", strip=True)
        if (
            href
            and label
            and any(ext in href.casefold() for ext in ("pluginfile.php", ".pdf", ".doc", ".zip"))
        ):
            files.append({"name": label, "url": href})
    return {
        "url": assignment_url,
        "title": title_node.get_text(" ", strip=True) if title_node else "",
        "instructions": description.get_text("\n", strip=True) if description else "",
        "attached_files": files,
        "submitted_files": _extract_submitted_file_names(response.text),
        "submission_status": parse_submission_status(response.text, profile),
    }


def _extract_submitted_file_names(html: str) -> List[str]:
    """Extrae nombres solo del bloque de archivos de la entrega del estudiante."""
    soup = BeautifulSoup(html or "", "lxml")
    labels = {
        "archivos enviados",
        "archivos de la entrega",
        "file submissions",
        "submission files",
        "submitted files",
    }
    names: List[str] = []
    for table in soup.select(".submissionstatustable, table.generaltable, table"):
        for row in table.select("tr"):
            cells = row.find_all(["th", "td"], recursive=False)
            if len(cells) < 2:
                cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = " ".join(cells[0].get_text(" ", strip=True).casefold().split())
            if label not in labels:
                continue
            values = cells[-1].select("a, .fp-filename, .fileuploadsubmission")
            names.extend(
                value.get_text(" ", strip=True)
                for value in values
                if value.get_text(" ", strip=True)
            )
    return list(dict.fromkeys(names))


def _click_button(page: Any, labels: tuple[str, ...]) -> None:
    pattern = re.compile("|".join(re.escape(label) for label in labels), re.IGNORECASE)
    for locator in page.locator("button, input[type='submit'], a.btn").all():
        try:
            label = locator.inner_text(timeout=500) or locator.get_attribute("value") or ""
            if pattern.search(label.strip()):
                locator.click()
                return
        except Exception:
            continue
    raise RuntimeError(f"Moodle no mostró una acción disponible ({', '.join(labels)})")


def _click_visible_text(page: Any, text: str) -> None:
    """Hace clic en el primer control visible con el texto indicado."""
    locator = page.get_by_text(text, exact=True)
    for index in range(locator.count()):
        item = locator.nth(index)
        if item.is_visible():
            item.click()
            return
    raise RuntimeError(f"Moodle no mostró el control esperado: {text}")


def _wait_for_visible_text(page: Any, text: str, timeout_ms: int) -> bool:
    """Espera un texto dentro de un ámbito y devuelve False si no aparece."""
    try:
        page.get_by_text(text, exact=True).wait_for(state="visible", timeout=timeout_ms)
        return True
    except Exception:
        return False


def _wait_for_submission_filemanager(page: Any) -> Any:
    """Espera la inserción y carga completa del filemanager de la entrega."""
    modern_selector = "[data-fieldtype='filemanager'] .filemanager:not(.fp-select)"
    modern = page.locator(modern_selector)
    try:
        modern.first.wait_for(state="attached", timeout=30000)
    except Exception:
        # Algunas versiones antiguas de Moodle no envuelven el campo con
        # data-fieldtype. Solo entonces se permite buscar el widget legacy.
        pass

    if modern.count():
        manager_selector = (
            "[data-fieldtype='filemanager'] .filemanager.fm-loaded"
            ":not(.fm-loading):not(.fm-updating)"
        )
    else:
        legacy_selector = ".filemanager:not(.fp-select)"
        legacy = page.locator(legacy_selector)
        try:
            legacy.first.wait_for(state="attached", timeout=30000)
        except Exception:
            pass
        if not legacy.count():
            return None
        manager_selector = (
            ".filemanager:not(.fp-select).fm-loaded:not(.fm-loading):not(.fm-updating)"
        )

    manager = page.locator(manager_selector).first
    manager.wait_for(state="visible", timeout=30000)
    return manager


def _remove_existing_submission_files(page: Any) -> None:
    """Retira adjuntos previos antes de reemplazar, sin guardar si no se identifican."""
    selectors = (
        ".fp-file-delete",
        "[data-action='delete']",
        "button[aria-label*='Delete']",
        "button[aria-label*='Eliminar']",
        "a[title*='Delete']",
        "a[title*='Eliminar']",
    )
    delete_buttons = None
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count():
            delete_buttons = locator
            break
    if delete_buttons is None:
        raise RuntimeError(
            "No se identificaron los archivos actuales para reemplazarlos con seguridad"
        )
    while delete_buttons.count():
        before_count = delete_buttons.count()
        delete_buttons.first.click()
        _click_button(page, ("Delete", "Eliminar", "Remove", "Quitar", "Sí", "Yes"))
        if delete_buttons.count() >= before_count:
            raise RuntimeError("Moodle no confirmó el retiro de los archivos existentes")


def _upload_submission_files(page: Any, files: Sequence[Path]) -> None:
    """Adjunta archivos desde el gestor nativo de archivos de Moodle."""
    # Moodle termina de inicializar el filemanager de forma asíncrona después
    # de que Playwright considera cargada la página. Evita abrir el selector
    # mientras el widget aún muestra "Cargando...".
    manager = _wait_for_submission_filemanager(page)
    if manager is None:
        # Algunos LMS antiguos usan un input dedicado sin filemanager. Excluye
        # el input repo_upload_file, que solo pertenece al diálogo Moodle.
        file_input = page.locator("input[type='file']:not([name='repo_upload_file'])").first
        if not file_input.count():
            raise RuntimeError("Moodle no mostró el gestor ni un campo directo de archivo")
        file_input.set_input_files([str(path) for path in files])
        for path in files:
            page.get_by_text(path.name, exact=True).wait_for(state="visible", timeout=30000)
        return

    add_file = manager.locator(".fp-btn-add a")

    if add_file.count():
        for path in files:
            add_file.first.click()
            dialog = page.locator(".moodle-dialogue-wrap.yui3-widget-content-expanded").last
            dialog.wait_for(state="visible", timeout=30000)
            _click_visible_text(dialog, "Subir un archivo")
            upload_input = dialog.locator("input[type='file'][name='repo_upload_file']")
            upload_input.wait_for(state="attached", timeout=30000)
            file_label = dialog.locator(".fp-file label").first
            file_label.wait_for(state="visible", timeout=30000)
            # Moodle's filepicker listens for the real filechooser change event;
            # set_input_files populated input.files but was rejected as empty.
            # In the native template, this visible label is associated with the
            # hidden repo_upload_file input and is the supported click target.
            with page.expect_file_chooser(timeout=30000) as chooser_info:
                file_label.click()
            chooser_info.value.set_files(str(path))
            selected_names = upload_input.evaluate(
                "input => Array.from(input.files).map(file => file.name)"
            )
            if path.name not in selected_names:
                try:
                    page.wait_for_function(
                        "expected => [...document.querySelectorAll("
                        "\"input[type='file'][name='repo_upload_file']\")].some("
                        "input => Array.from(input.files).some(file => file.name === expected))",
                        arg=path.name,
                        timeout=5000,
                    )
                except Exception as error:
                    selected_names = upload_input.evaluate(
                        "input => Array.from(input.files).map(file => file.name)"
                    )
                    raise RuntimeError(
                        f"Playwright no dejó {path.name} seleccionado en Moodle; "
                        f"el input reportó {selected_names}"
                    ) from error
                selected_names = upload_input.evaluate(
                    "input => Array.from(input.files).map(file => file.name)"
                )
            if path.name not in selected_names:
                raise RuntimeError(
                    f"Playwright no dejó {path.name} seleccionado en Moodle; "
                    f"el input reportó {selected_names}"
                )
            _click_button(dialog, ("Subir este archivo", "Upload this file"))
            # Moodle primero recibe el archivo en el selector y luego lo
            # adjunta al borrador al confirmar "Seleccionar". Espera ambos
            # pasos y verifica el nombre en el filemanager de la entrega.
            selection_dialog = page.locator(
                ".moodle-dialogue-wrap.yui3-widget-content-expanded"
            ).last
            try:
                selection_dialog.wait_for(state="visible", timeout=5000)
            except Exception:
                selection_dialog = None
            if selection_dialog is not None:
                # Some Moodle themes close the picker and attach the file
                # directly; others show a file detail dialog first.
                if _wait_for_visible_text(selection_dialog, path.name, timeout_ms=5000):
                    for label in ("Seleccionar este archivo", "Seleccionar"):
                        if _wait_for_visible_text(selection_dialog, label, timeout_ms=5000):
                            _click_visible_text(selection_dialog, label)
                            break
            manager.get_by_text(path.name, exact=True).wait_for(state="visible", timeout=30000)
        return
    raise RuntimeError("Moodle no mostró el control Agregar del gestor de archivos")


def manage_assignment_submission(
    action: str,
    assignment_url: str,
    base_url: str,
    username: str,
    password: str,
    auth_profile: Dict[str, Any],
    profile: Dict[str, Any],
    file_path: Optional[str] = None,
    confirmed: bool = False,
    headless: bool = True,
    timeout_ms: int = 15000,
    file_paths: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Crea, reemplaza o retira una entrega propia usando los controles de Moodle."""
    local_files = validate_submission_action(
        action, assignment_url, base_url, file_path, confirmed, file_paths
    )
    if action == "read":
        raise ValueError(
            "Para leer detalles use read_assignment_details con una sesión autenticada"
        )
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright es necesario para gestionar archivos en Moodle") from exc

    base = urlparse(base_url)
    portal_origin = f"{base.scheme}://{base.netloc}"
    login = f"{portal_origin}{auth_profile.get('login_path', '/login/')}"
    selectors = auth_profile.get("form_selectors", {})
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=headless)
        try:
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.goto(login, wait_until="domcontentloaded", timeout=timeout_ms)
            username_selector = selectors.get("username", "#username")
            password_selector = selectors.get("password", "#password")
            page.wait_for_selector(username_selector, timeout=timeout_ms)
            page.wait_for_selector(password_selector, timeout=timeout_ms)
            page.fill(username_selector, username)
            page.fill(password_selector, password)
            page.click(selectors.get("submit", "#loginbtn"))
            page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            page.goto(assignment_url, wait_until="domcontentloaded", timeout=timeout_ms)
            before = parse_submission_status(page.content(), profile)
            state = before.get("state", "unknown")
            try:
                validate_submission_action(
                    action,
                    assignment_url,
                    base_url,
                    file_path,
                    confirmed,
                    file_paths,
                    submission_state=state,
                )
            except ValueError as error:
                raise RuntimeError(f"El estado actual no permite esta acción: {state}") from error
            if state == "unknown":
                raise RuntimeError("El estado actual no permite esta acción o no se pudo verificar")

            action_labels = {
                "create": ("Add submission", "Agregar entrega", "Añadir entrega"),
                "update": ("Edit submission", "Editar entrega"),
                "delete": ("Remove submission", "Quitar entrega", "Eliminar entrega"),
            }
            _click_button(page, action_labels[action])
            if action == "delete":
                _click_button(page, ("Continue", "Continuar", "Sí", "Yes", "Remove submission"))
            else:
                if action == "update":
                    _remove_existing_submission_files(page)
                _upload_submission_files(page, local_files or [])
                _click_button(
                    page, ("Save changes", "Guardar cambios", "Submit assignment", "Guardar")
                )
                current = parse_submission_status(page.content(), profile)
                if current.get("state") not in {"submitted", "draft"}:
                    raise RuntimeError("Moodle no mostró la entrega guardada antes del envío")
                if current["state"] == "draft":
                    _click_button(
                        page,
                        (
                            "Submit assignment",
                            "Enviar tarea",
                            "Enviar entrega",
                            "Enviar para calificar",
                        ),
                    )
                    _click_button(
                        page,
                        ("Continue", "Continuar", "Confirm", "Confirmar", "Sí", "Yes"),
                    )

            try:
                page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
            except PlaywrightTimeout:
                pass
            page.goto(assignment_url, wait_until="domcontentloaded", timeout=timeout_ms)
            final_html = page.content()
            after = parse_submission_status(final_html, profile)
            submitted_files = _extract_submitted_file_names(final_html)
            if action == "delete":
                if after.get("state") != "not_submitted" or submitted_files:
                    raise RuntimeError("Moodle no confirmó el retiro de la entrega y sus archivos")
            else:
                expected_names = {path.name for path in local_files or []}
                if after.get("state") != "submitted" or expected_names != set(submitted_files):
                    raise RuntimeError(
                        "Moodle no confirmó el envío de todos los archivos; revisa la entrega"
                    )
            return {
                "action": action,
                "url": assignment_url,
                "submission_status": after,
                "submitted_files": submitted_files,
                "verified": True,
            }
        finally:
            browser.close()
