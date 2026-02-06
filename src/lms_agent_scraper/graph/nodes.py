"""Nodos del grafo LangGraph para el scraper."""
import logging
from pathlib import Path
from typing import Any, Dict

from lms_agent_scraper.graph.state import ScraperState
from lms_agent_scraper.tools.browser_tools import get_course_links_with_playwright, login_with_playwright

log = logging.getLogger(__name__)
from lms_agent_scraper.tools.extraction_tools import get_assignments_for_courses
from lms_agent_scraper.tools.report_tools import generate_markdown_report, save_report


def authentication_node(state: ScraperState) -> Dict[str, Any]:
    """
    Nodo de autenticación: login en el portal con Playwright usando perfil.
    """
    log.info("[1/5] Autenticación: iniciando login en el portal...")
    updates: Dict[str, Any] = {"errors": state.get("errors", [])}
    profile = state.get("profile") or {}
    auth = profile.get("auth", {})
    base_url = state.get("base_url", "")
    username = state.get("username", "")
    password = state.get("password", "")

    if not base_url or not username or not password:
        log.warning("[1/5] Autenticación: faltan base_url o credenciales, omitiendo.")
        updates["authenticated"] = False
        updates["session_cookies"] = []
        return updates

    try:
        result = login_with_playwright(
            base_url=base_url,
            username=username,
            password=password,
            auth_profile=auth,
            login_path=auth.get("login_path", "/login/"),
            headless=True,
            debug=state.get("_debug", False),
        )
        updates["authenticated"] = result.get("success", False)
        updates["session_cookies"] = result.get("cookies", [])
        if result.get("error"):
            updates["errors"] = updates["errors"] + [result["error"]]
        if updates["authenticated"]:
            log.info("[1/5] Autenticación: OK (sesión iniciada).")
        else:
            log.warning("[1/5] Autenticacion: fallo - %s", result.get("error", "redireccion inesperada"))
    except Exception as e:
        log.exception("[1/5] Autenticacion: error - %s", e)
        updates["errors"] = updates["errors"] + [f"Auth error: {e}"]
        updates["authenticated"] = False
        updates["session_cookies"] = []
    return updates


def course_discovery_node(state: ScraperState) -> Dict[str, Any]:
    """
    Nodo de descubrimiento de cursos: obtiene la lista de cursos con Playwright.
    """
    log.info("[2/5] Descubrimiento de cursos: iniciando (abriendo /my/courses.php)...")
    updates: Dict[str, Any] = {"errors": state.get("errors", [])}
    if not state.get("authenticated"):
        log.warning("[2/5] Descubrimiento de cursos: omitido (no hay sesión).")
        updates["courses"] = []
        return updates

    profile = state.get("profile") or {}
    navigation = profile.get("navigation", {})
    courses_config = profile.get("courses", {})
    base_url = state.get("base_url", "")
    cookies = state.get("session_cookies", [])

    try:
        courses = get_course_links_with_playwright(
            base_url=base_url,
            navigation_profile=navigation,
            courses_profile=courses_config,
            cookies=cookies,
            headless=True,
            debug=state.get("_debug", False),
        )
        updates["courses"] = courses
        log.info("[2/5] Descubrimiento de cursos: listo - %d curso(s) encontrado(s).", len(courses))
    except Exception as e:
        log.exception("[2/5] Descubrimiento de cursos: error - %s", e)
        updates["errors"] = updates["errors"] + [f"Course discovery error: {e}"]
        updates["courses"] = []
    return updates


def assignment_extractor_node(state: ScraperState) -> Dict[str, Any]:
    """
    Nodo de extracción de tareas: por cada curso extrae assignments con requests + BeautifulSoup.
    """
    courses = state.get("courses", [])
    log.info("[3/5] Extracción de tareas: iniciando (recorriendo %d curso(s))...", len(courses))
    updates: Dict[str, Any] = {"errors": state.get("errors", [])}
    if not courses:
        log.info("[3/5] Extracción de tareas: no hay cursos, omitiendo.")
        updates["assignments"] = []
        return updates

    profile = state.get("profile") or {}
    cookies = state.get("session_cookies", [])
    base_url = state.get("base_url", "")
    max_courses = state.get("max_courses", 0)

    try:
        assignments = get_assignments_for_courses(
            courses=courses,
            cookies=cookies,
            profile=profile,
            base_url=base_url,
            max_courses=max_courses,
        )
        updates["assignments"] = assignments
        log.info("[3/5] Extraccion de tareas: listo - %d tarea(s) extraida(s).", len(assignments))
    except Exception as e:
        log.exception("[3/5] Extraccion de tareas: error - %s", e)
        updates["errors"] = updates["errors"] + [f"Extraction error: {e}"]
        updates["assignments"] = []
    return updates


def data_processor_node(state: ScraperState) -> Dict[str, Any]:
    """
    Nodo de procesamiento: el filtrado por fecha se hace en el reporte.
    """
    log.info("[4/5] Procesamiento de datos: (sin lógica adicional, filtrado en reporte).")
    return {}


def report_generator_node(state: ScraperState) -> Dict[str, Any]:
    """
    Nodo de generación de reporte: Markdown y guardado en output_dir.
    """
    log.info("[5/5] Generación de reporte: generando Markdown y guardando...")
    updates: Dict[str, Any] = {"errors": state.get("errors", [])}
    assignments = state.get("assignments", [])
    days_ahead = state.get("days_ahead", 7)
    days_behind = state.get("days_behind", 7)
    output_dir = state.get("output_dir", "reports")
    profile = state.get("profile") or {}
    reports_config = profile.get("reports", {})
    title_tpl = reports_config.get("title_template", "Reporte de Tareas - {portal_name}")
    title = title_tpl.format(portal_name=state.get("base_url", "").replace("https://", "").split("/")[0] or "LMS")

    try:
        content = generate_markdown_report(
            assignments,
            days_ahead=days_ahead,
            days_behind=days_behind,
            all_assignments=assignments,
            title=title,
        )
        report_path = save_report(content, output_dir=output_dir)
        updates["report_path"] = report_path
        log.info("[5/5] Generacion de reporte: listo - %s", report_path)
    except Exception as e:
        log.exception("[5/5] Generacion de reporte: error - %s", e)
        updates["errors"] = updates["errors"] + [f"Report error: {e}"]
        updates["report_path"] = ""
    return updates
