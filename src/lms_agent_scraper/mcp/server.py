"""
Servidor MCP para LMS Agent Scraper.
Expone herramientas: get_pending_assignments, get_submitted_assignments, get_courses, generate_report, check_deadlines, list_profiles.
"""
from pathlib import Path
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from lms_agent_scraper.config.settings import PortalSettings, ScraperSettings, OutputSettings
from lms_agent_scraper.core.profile_loader import ProfileLoader
from lms_agent_scraper.graph.workflow import run_workflow
from lms_agent_scraper.tools.report_tools import filter_by_date

MCP_INSTRUCTIONS = """
Este servidor MCP da acceso al portal LMS de la Universidad Simón Bolívar (Unisimon), Aula Pregrado.
Usa las herramientas para consultar tareas pendientes, cursos, entregas y plazos del estudiante en ese portal.
Contexto: Unisimon, Universidad Simón Bolívar, Colombia.
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


def _run_full_workflow() -> Dict[str, Any]:
    """Ejecuta el workflow completo usando configuración de entorno."""
    portal = PortalSettings()
    scraper = ScraperSettings()
    output = OutputSettings()
    if not portal.base_url or not portal.username:
        return {"error": "Configure PORTAL_BASE_URL, PORTAL_USERNAME, PORTAL_PASSWORD"}
    return run_workflow(
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


@mcp.tool()
def get_pending_assignments(days_ahead: int = 7, days_behind: int = 0) -> str:
    """
    Obtiene las tareas pendientes (atrasadas, vencen hoy, próximas) del portal LMS configurado.
    days_ahead: días hacia adelante; days_behind: días hacia atrás para atrasadas.
    """
    result = _run_full_workflow()
    if result.get("error"):
        return str(result)
    assignments = result.get("assignments", [])
    filtered = filter_by_date(assignments, days_ahead=days_ahead, days_behind=days_behind)
    return _format_assignments(filtered)


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
        a for a in assignments
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
        lines.append(f"- {a.get('title', 'N/A')} | {a.get('course', 'N/A')} | {a.get('due_date', '')} | {a.get('url', '')}")
    return "\n".join(lines)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
