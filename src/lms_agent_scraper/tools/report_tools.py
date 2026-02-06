"""
Generación de reportes en Markdown (y opcionalmente JSON).
"""
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List

from lms_agent_scraper.core.date_parser import parse_date


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


def generate_markdown_report(
    assignments: List[Dict[str, Any]],
    days_ahead: int,
    days_behind: int,
    all_assignments: List[Dict[str, Any]] = None,
    title: str = "Reporte de Tareas",
) -> str:
    """Genera el contenido Markdown del reporte."""
    all_assignments = all_assignments or assignments
    filtered = filter_by_date(assignments, days_ahead, days_behind)
    overdue = [a for a in filtered if a.get("status") == "OVERDUE"]
    due_today = [a for a in filtered if a.get("status") == "DUE_TODAY"]
    upcoming = [a for a in filtered if a.get("status") == "UPCOMING"]
    recently_submitted = [
        a for a in (all_assignments or [])
        if (a.get("submission_status") or {}).get("submitted")
        and ((a.get("submission_status") or {}).get("days_ago") or 999) <= 7
    ]

    lines = [
        f"# {title}",
        "",
        f"**Fecha de generación:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
        f"**Período:** Últimos {days_behind} días y próximos {days_ahead} días",
        f"**Total tareas:** {len(all_assignments)}",
        "",
        "---",
        "",
    ]
    if recently_submitted:
        lines.append("## Tareas Entregadas Recientemente (Últimos 7 días)")
        lines.append("")
        for a in recently_submitted:
            lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
            lines.append(f"  - *Estado:* {(a.get('submission_status') or {}).get('status_text', 'N/A')}")
            lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
        lines.append("")
        lines.append("---")
        lines.append("")
    if overdue:
        lines.append("## Tareas Atrasadas")
        lines.append("")
        for a in overdue:
            lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
            lines.append(f"  - *Vencida hace:* {a.get('days_overdue', 0)} días")
            lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
        lines.append("")
    if due_today:
        lines.append("## Tareas que Vencen Hoy")
        lines.append("")
        for a in due_today:
            lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
            lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
        lines.append("")
    if upcoming:
        lines.append("## Próximas Tareas")
        lines.append("")
        for a in upcoming:
            lines.append(f"- **{a.get('title', 'N/A')}** en **{a.get('course', 'N/A')}**")
            lines.append(f"  - *Vence en:* {a.get('days_until_due', 0)} días")
            lines.append(f"  - *URL:* {a.get('url', 'N/A')}")
        lines.append("")
    if not (overdue or due_today or upcoming or recently_submitted):
        lines.append("## Sin tareas pendientes en el período consultado.")
        lines.append("")
    lines.append("*Reporte generado por LMS Agent Scraper*")
    return "\n".join(lines)


def save_report(content: str, output_dir: str = "reports", prefix: str = "assignments_report") -> str:
    """Guarda el reporte en un archivo y devuelve la ruta."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out / f"{prefix}_{timestamp}.md"
    path.write_text(content, encoding="utf-8")
    return str(path)
