"""
Generación de reportes en Markdown (y opcionalmente JSON).
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from lms_agent_scraper.core.date_parser import parse_date
from lms_agent_scraper.core.skill_loader import SkillLoader


def filter_by_date(
    assignments: List[Dict[str, Any]],
    days_ahead: int,
    days_behind: int = 0,
) -> List[Dict[str, Any]]:
    """Filtra assignments por ventana de fechas y añade status (OVERDUE, DUE_TODAY, UPCOMING)."""
    if not assignments:
        return []
    today = datetime.now().date()
    future_cutoff = today + timedelta(days=days_ahead)
    past_cutoff = today - timedelta(days=days_behind)
    filtered = []
    for a in assignments:
        due = parse_date(a.get("due_date", ""))
        if due:
            d = due.date() if hasattr(due, "date") else due
        else:
            continue
        if (d <= future_cutoff and d >= today) or (d < today and d >= past_cutoff):
            ac = dict(a)
            if d < today:
                ac["status"] = "OVERDUE"
                ac["days_overdue"] = (today - d).days
            elif d == today:
                ac["status"] = "DUE_TODAY"
                ac["days_until_due"] = 0
            else:
                ac["status"] = "UPCOMING"
                ac["days_until_due"] = (d - today).days
            filtered.append(ac)
    return filtered


def count_tasks_in_period(
    assignments: List[Dict[str, Any]],
    days_ahead: int,
    days_behind: int,
) -> int:
    """
    Devuelve el número de tareas en el período del reporte (mismo criterio que "Total tareas").
    Incluye atrasadas, vencen hoy, próximas y entregadas recientemente (últimos 7 días).
    """
    if not assignments:
        return 0
    filtered = filter_by_date(assignments, days_ahead, days_behind)
    overdue = [a for a in filtered if a.get("status") == "OVERDUE"]
    due_today = [a for a in filtered if a.get("status") == "DUE_TODAY"]
    upcoming = [a for a in filtered if a.get("status") == "UPCOMING"]
    recently_submitted = [
        a
        for a in assignments
        if (a.get("submission_status") or {}).get("submitted")
        and ((a.get("submission_status") or {}).get("days_ago") or 999) <= 7
    ]
    return len(overdue) + len(due_today) + len(upcoming) + len(recently_submitted)


def render_report_from_template(template_str: str, context: Dict[str, Any]) -> str:
    """
    Rellena la plantilla del reporte con el contexto usando str.format().

    Args:
        template_str: Texto de la plantilla con placeholders {nombre}.
        context: Diccionario con todas las variables (title, generation_date, etc.).

    Returns:
        Reporte Markdown completo.
    """
    return template_str.format(**context)


def _build_section_recently_submitted(
    recently_submitted: List[Dict[str, Any]],
) -> str:
    """Construye el bloque Markdown de tareas entregadas recientemente."""
    if not recently_submitted:
        return ""
    lines = ["## Tareas Entregadas Recientemente (Últimos 7 días)", ""]
    for a in recently_submitted:
        lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
        lines.append(
            f"  - *Estado:* {(a.get('submission_status') or {}).get('status_text', 'N/A')}"
        )
        lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _build_section_overdue(overdue: List[Dict[str, Any]]) -> str:
    """Construye el bloque Markdown de tareas atrasadas."""
    if not overdue:
        return ""
    lines = ["## Tareas Atrasadas", ""]
    for a in overdue:
        lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
        lines.append(f"  - *Vencida hace:* {a.get('days_overdue', 0)} días")
        lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
    lines.append("")
    return "\n".join(lines)


def _build_section_due_today(due_today: List[Dict[str, Any]]) -> str:
    """Construye el bloque Markdown de tareas que vencen hoy."""
    if not due_today:
        return ""
    lines = ["## Tareas que Vencen Hoy", ""]
    for a in due_today:
        lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
        lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
    lines.append("")
    return "\n".join(lines)


def _build_section_upcoming(upcoming: List[Dict[str, Any]]) -> str:
    """Construye el bloque Markdown de próximas tareas."""
    if not upcoming:
        return ""
    lines = ["## Próximas Tareas", ""]
    for a in upcoming:
        lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
        lines.append(f"  - *Vence en:* {a.get('days_until_due', 0)} días")
        lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
    lines.append("")
    return "\n".join(lines)


def _build_courses_explored_section(courses: Optional[List[Dict[str, Any]]]) -> str:
    """Construye la sección Markdown con la lista de cursos explorados. Siempre visible."""
    lines = ["## Cursos explorados", ""]
    if not courses:
        lines.append("No se encontraron cursos explorados.")
    else:
        for c in courses:
            name = c.get("name") or c.get("title") or "Sin nombre"
            lines.append(f"- {name}")
    lines.append("")
    return "\n".join(lines)


def generate_markdown_report(
    assignments: List[Dict[str, Any]],
    days_ahead: int,
    days_behind: int,
    all_assignments: List[Dict[str, Any]] = None,
    title: str = "Reporte de Tareas",
    courses_count: int = None,
    courses: Optional[List[Dict[str, Any]]] = None,
    template_loader: Optional[SkillLoader] = None,
) -> str:
    """Genera el contenido Markdown del reporte usando la plantilla del skill report-generator."""
    all_assignments = all_assignments or assignments
    filtered = filter_by_date(assignments, days_ahead, days_behind)
    overdue = [a for a in filtered if a.get("status") == "OVERDUE"]
    due_today = [a for a in filtered if a.get("status") == "DUE_TODAY"]
    upcoming = [a for a in filtered if a.get("status") == "UPCOMING"]
    recently_submitted = [
        a
        for a in (all_assignments or [])
        if (a.get("submission_status") or {}).get("submitted")
        and ((a.get("submission_status") or {}).get("days_ago") or 999) <= 7
    ]

    generation_date = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    period = f"Últimos {days_behind} días y próximos {days_ahead} días"
    courses_count_line = (
        f"**Cursos encontrados:** {courses_count}" if courses_count is not None else ""
    )
    courses_explored_section = _build_courses_explored_section(courses)
    has_any = bool(overdue or due_today or upcoming or recently_submitted)
    empty_message = "## Sin tareas pendientes en el período consultado.\n\n" if not has_any else ""
    footer = "*Reporte generado por LMS Agent Scraper*"

    tasks_in_period = len(overdue) + len(due_today) + len(upcoming) + len(recently_submitted)
    context = {
        "title": title,
        "generation_date": generation_date,
        "period": period,
        "total_tasks": tasks_in_period,
        "courses_count_line": courses_count_line,
        "courses_explored_section": courses_explored_section,
        "section_recently_submitted": _build_section_recently_submitted(recently_submitted),
        "section_overdue": _build_section_overdue(overdue),
        "section_due_today": _build_section_due_today(due_today),
        "section_upcoming": _build_section_upcoming(upcoming),
        "empty_message": empty_message,
        "footer": footer,
    }

    loader = template_loader or SkillLoader()
    template_str = loader.load_skill_resource("report-generator", "report_template.md")
    if not template_str:
        raise FileNotFoundError(
            "No se encontró la plantilla del reporte. Asegúrate de que existe el recurso "
            "report_template.md en el skill report-generator (src/lms_agent_scraper/skills/report-generator/)."
        )
    return render_report_from_template(template_str, context)


def save_report(
    content: str, output_dir: str = "reports", prefix: str = "assignments_report"
) -> str:
    """Guarda el reporte en un archivo y devuelve la ruta."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out / f"{prefix}_{timestamp}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)
