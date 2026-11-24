"""
Servidor MCP para LMS Agent Scraper.
Expone herramientas: get_pending_assignments, get_submitted_assignments, get_courses, generate_report, check_deadlines, list_profiles.
"""

import json
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from mcp.server.fastmcp import FastMCP

from lms_agent_scraper.config.settings import PortalSettings, ScraperSettings, OutputSettings
from lms_agent_scraper.core.profile_loader import ProfileLoader
from lms_agent_scraper.graph.workflow import run_workflow
from lms_agent_scraper.tools.report_tools import filter_by_date
from lms_agent_scraper.tools.extraction_tools import session_from_cookies
from lms_agent_scraper.tools.moodle_submission import (
    manage_assignment_submission as perform_submission_action,
    read_assignment_details,
    validate_submission_action,
)
from lms_agent_scraper.tools.submission_tools import filter_pending_assignments

MCP_INSTRUCTIONS = """
Este servidor MCP da acceso a portales LMS Moodle: cursos, tareas pendientes, entregas y plazos del estudiante.
La configuración de ejemplo puede usar el perfil moodle_unisimon (Universidad Simón Bolívar, Colombia, Aula Extendida);
puedes configurar otro perfil y URL para cualquier Moodle.
Para el flujo completo, consulta primero get_assignment_workflow y sigue sus pasos. Usa get_pending_assignments para listar y read_assignment para consultar instrucciones. Las operaciones se limitan a entregas propias que el scraper descubrió en el portal configurado; create, update y delete requieren confirmed=true.
"""

mcp = FastMCP(
    "lms-agent-scraper",
    instructions=MCP_INSTRUCTIONS.strip(),
    json_response=True,
)


def _profiles_dir() -> Path:
    root = Path(__file__).resolve().parent.parent.parent
    if (root / "profiles").exists():
        return root / "profiles"
    return Path("profiles")


def _normalize_course_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", (value or "").casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


@mcp.tool()
def get_assignment_workflow() -> str:
    """Devuelve el skill assignment-manager con el flujo de lectura, preparación y gestión segura."""
    skill_path = Path(__file__).resolve().parent.parent / "skills" / "assignment-manager" / "SKILL.md"
    try:
        return skill_path.read_text(encoding="utf-8")
    except OSError:
        return "No se encontró el skill assignment-manager en la instalación del paquete."


def _run_full_workflow() -> Dict[str, Any]:
    """Ejecuta el workflow completo usando configuración de entorno."""
    portal = PortalSettings()
    scraper = ScraperSettings()
    output = OutputSettings()
    if not portal.base_url or not portal.username or not portal.password:
        return {"error": "Configure PORTAL_BASE_URL, PORTAL_USERNAME, PORTAL_PASSWORD"}
    result = run_workflow(
        profile_name=portal.profile,
        base_url=portal.base_url,
        username=portal.username,
        password=portal.password,
        days_ahead=scraper.days_ahead,
        days_behind=scraper.days_behind,
        max_courses=scraper.max_courses,
        output_dir=str(output.dir),
        profiles_dir=_profiles_dir(),
        debug=False,
    )
    errors = list(result.get("errors") or [])
    if result.get("authenticated") is not True:
        errors.append("Authentication error: no hay una sesión autenticada")
    if not result.get("courses"):
        errors.append("Course discovery error: el portal no devolvió cursos")
    unknown_assignments = [
        item
        for item in result.get("assignments", [])
        if item.get("type") == "assignment"
        and (
            (item.get("submission_status") or {}).get("state") == "unknown"
            or (item.get("submission_status") or {}).get("submitted") is None
        )
    ]
    if errors or unknown_assignments:
        details = "; ".join(str(error) for error in errors)
        if unknown_assignments:
            names = ", ".join(
                item.get("title", "entrega sin nombre")
                for item in unknown_assignments[:5]
            )
            details = f"{details}; " if details else ""
            details += f"no se pudo confirmar el estado de {len(unknown_assignments)} entrega(s): {names}"
        return {
            "error": f"Scraper incompleto; no se presentará una lista como completa. {details}",
            "report_path": result.get("report_path", ""),
        }
    return result


@mcp.tool()
def get_pending_assignments(
    days_ahead: int = 60,
    days_behind: int = 120,
    course_names: str = "",
) -> str:
    """Lista entregas no enviadas de los cursos indicados dentro de la ventana de fechas.

    course_names acepta nombres separados por comas. Si se omite, usa SCRAPER_TARGET_COURSES;
    si esa variable también está vacía, incluye todos los cursos descubiertos.
    """
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    configured_names = course_names or ScraperSettings().target_courses
    names = [name.strip() for name in configured_names.split(",") if name.strip()]
    all_discovered_courses = result.get("courses", [])
    max_courses = ScraperSettings().max_courses
    processed_courses = (
        all_discovered_courses[:max_courses]
        if max_courses > 0
        else all_discovered_courses
    )
    discovered_courses = [
        _normalize_course_name(course.get("name", ""))
        for course in processed_courses
    ]
    missing_courses = [
        name
        for name in names
        if not any(_normalize_course_name(name) in course for course in discovered_courses)
    ]
    if names and missing_courses:
        return (
            "Scraper incompleto; no se encontraron los cursos solicitados: "
            + ", ".join(missing_courses)
        )
    filtered = filter_pending_assignments(
        result.get("assignments", []), names, days_ahead=days_ahead, days_behind=days_behind
    )
    return _format_assignments(filtered)


@mcp.tool()
def read_assignment(assignment_url: str) -> str:
    """Lee instrucciones, archivos asociados y estado de una entrega descubierta."""
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    assignment = _find_target_assignment(result, assignment_url)
    if not assignment:
        return "La URL no pertenece a una entrega descubierta en el portal configurado."
    portal = PortalSettings()
    try:
        validate_submission_action("read", assignment_url, portal.base_url, None, False)
    except ValueError as error:
        return str(error)
    session = session_from_cookies(result.get("session_cookies", []), portal.base_url)
    details = read_assignment_details(assignment_url, session, result.get("profile", {}))
    details["course"] = assignment.get("course", "")
    return json.dumps(details, ensure_ascii=False)


@mcp.tool()
def manage_submission(
    action: str,
    assignment_url: str,
    file_path: str = "",
    confirmed: bool = False,
    file_paths: Optional[List[str]] = None,
) -> str:
    """Crea o reemplaza una entrega propia con hasta cinco archivos; requiere confirmed=true."""
    if action not in {"create", "update", "delete"}:
        return "Acción inválida: usa create, update o delete."
    if not confirmed:
        return "Acción detenida: requiere confirmación explícita del usuario (confirmed=true)."
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    assignment = _find_target_assignment(result, assignment_url)
    if not assignment:
        return "La URL no pertenece a una entrega descubierta en el portal configurado."
    portal = PortalSettings()
    profile = result.get("profile", {})
    try:
        outcome = perform_submission_action(
            action=action,
            assignment_url=assignment_url,
            base_url=portal.base_url,
            username=portal.username,
            password=portal.password,
            auth_profile=profile.get("auth", {}),
            profile=profile,
            file_path=file_path or None,
            file_paths=file_paths,
            confirmed=confirmed,
        )
    except Exception as error:
        return f"No se completó la acción: {error}"
    return json.dumps(outcome, ensure_ascii=False)


def _find_target_assignment(result: Dict[str, Any], assignment_url: str) -> Dict[str, Any]:
    """Permite operar solo sobre una entrega descubierta en el recorrido actual."""
    def normalized(url: str) -> str:
        parts = urlparse(url)
        return urlunparse(
            (
                parts.scheme.casefold(),
                parts.netloc.casefold(),
                parts.path,
                "",
                parts.query,
                "",
            )
        )

    target = normalized(assignment_url)
    for assignment in result.get("assignments", []):
        if (
            assignment.get("type") != "assignment"
            or normalized(assignment.get("url", "")) != target
        ):
            continue
        return assignment
    return {}


@mcp.tool()
def get_submitted_assignments(days: int = 7) -> str:
    """
    Obtiene las tareas entregadas recientemente (últimos N días).
    """
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    assignments = result.get("assignments", [])
    submitted = [
        a
        for a in assignments
        if (a.get("submission_status") or {}).get("submitted")
        and ((a.get("submission_status") or {}).get("days_ago") or 999) <= days
    ]
    return _format_assignments(submitted)


@mcp.tool()
def get_courses() -> str:
    """
    Lista los cursos disponibles en el portal LMS configurado.
    """
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    courses = result.get("courses", [])
    if not courses:
        return "No se encontraron cursos o el login falló."
    lines = [f"- {c.get('name', 'N/A')}: {c.get('url', 'N/A')}" for c in courses]
    return "\n".join(lines)


@mcp.tool()
def generate_report(format: str = "markdown", days_ahead: int = 7, days_behind: int = 7) -> str:
    """
    Genera un reporte de tareas y devuelve la ruta del archivo guardado.
    format: 'markdown' (por ahora solo markdown).
    """
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    report_path = result.get("report_path", "")
    if report_path:
        return f"Reporte guardado en: {report_path}"
    return "No se generó reporte (sin tareas o error)."


@mcp.tool()
def check_deadlines(days: int = 7) -> str:
    """
    Verifica deadlines en los próximos N días y devuelve un resumen.
    """
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    assignments = result.get("assignments", [])
    filtered = filter_by_date(assignments, days_ahead=days, days_behind=0)
    overdue = len([a for a in filtered if a.get("status") == "OVERDUE"])
    due_today = len([a for a in filtered if a.get("status") == "DUE_TODAY"])
    upcoming = len([a for a in filtered if a.get("status") == "UPCOMING"])
    return f"Atrasadas: {overdue} | Vencen hoy: {due_today} | Próximas ({days} días): {upcoming}"


@mcp.tool()
def list_profiles() -> str:
    """
    Lista los perfiles de portal disponibles (YAML en profiles/).
    """
    loader = ProfileLoader(_profiles_dir())
    names = loader.list_profiles()
    if not names:
        return "No hay perfiles en el directorio profiles/."
    return "\n".join(names)


def _format_assignments(assignments: List[Dict[str, Any]]) -> str:
    if not assignments:
        return "No hay tareas en el criterio indicado."
    lines = []
    for a in assignments:
        due_text = a.get("due_relative") or a.get("due_date", "")
        lines.append(
            f"- {a.get('status', 'PENDING')} | {a.get('title', 'N/A')} | "
            f"{a.get('course', 'N/A')} | {due_text} | {a.get('url', '')}"
        )
    return "\n".join(lines)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
