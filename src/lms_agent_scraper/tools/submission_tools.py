"""Lectura y filtrado del estado de entregas de Moodle."""

import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from bs4 import BeautifulSoup

from lms_agent_scraper.core.date_parser import extract_date_from_text, parse_date


def enrich_assignment_submission_status(
    assignments: Iterable[Dict[str, Any]],
    session: Any,
    profile: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """Consulta la página de detalle de cada tarea y adjunta su estado real."""
    enriched: List[Dict[str, Any]] = []
    for assignment in assignments:
        item = dict(assignment)
        if item.get("type") != "assignment":
            item["submission_status"] = {
                "submitted": None,
                "status_text": "El estado no aplica a esta actividad",
            }
            enriched.append(item)
            continue
        try:
            response = session.get(item["url"], timeout=timeout)
            response.raise_for_status()
            item["submission_status"] = parse_submission_status(response.text, profile)
            if not item.get("due_date"):
                due_date = _extract_due_date(response.text, (profile or {}).get("dates", {}))
                if due_date:
                    item["due_date"] = due_date
                else:
                    item.update(_parse_relative_due_time(response.text) or {})
        except Exception:
            item["submission_status"] = {
                "submitted": None,
                "state": "unknown",
                "status_text": "No se pudo consultar el estado de entrega",
            }
        enriched.append(item)
    return enriched


DEFAULT_SUBMITTED_INDICATORS = (
    "enviado para calificar",
    "enviada para calificar",
    "submitted for grading",
    "submitted",
    "entregado",
    "entregada",
)
DEFAULT_PENDING_INDICATORS = (
    "no entregado",
    "no entregada",
    "no se ha enviado",
    "todavía no se han realizado envíos",
    "no se han realizado envíos",
    "not submitted",
    "draft (not submitted)",
)
DEFAULT_DRAFT_INDICATORS = ("borrador", "draft")
DEFAULT_EMPTY_INDICATORS = ("no hay envios", "no hay envíos", "sin envios", "sin envíos")


def _extract_due_date(html: str, date_config: Dict[str, Any]) -> str:
    """Prioriza la fecha de cierre de Moodle sobre la fecha de apertura."""
    text = BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)
    date_pattern = (
        r"(\d{1,2}\s+de\s+[\wáéíóúüñ]+\s+de\s+\d{4}|"
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
    )
    due_context = re.search(
        rf"(?:cierre|vencimiento|fecha de entrega|fecha límite|due date|deadline)"
        rf"[^0-9]{{0,100}}{date_pattern}",
        text,
        re.IGNORECASE,
    )
    if due_context:
        return due_context.group(1)
    return extract_date_from_text(text, date_config.get("patterns", [])) or ""


def _parse_relative_due_time(html: str) -> Optional[Dict[str, Any]]:
    """Lee el contador de Moodle sin transformarlo en una fecha absoluta inventada."""
    text = BeautifulSoup(html or "", "lxml").get_text(" ", strip=True)
    timer = re.search(
        r"(?:tiempo restante|time remaining)\s*:?\s*(.*?)(?=\s+(?:"
        r"última modificación|comentarios|estado de la calificación|last modified|comments)\b|$)",
        text,
        re.IGNORECASE,
    )
    if not timer:
        return None
    relative_text = timer.group(1).strip()
    durations = re.findall(
        r"(\d+)\s*(d[ií]as?|days?|horas?|hours?|min(?:utos?)?|minutes?)",
        relative_text,
        re.IGNORECASE,
    )
    if not durations:
        return None
    days = hours = minutes = 0
    for value, unit in durations:
        if unit.casefold().startswith("d"):
            days += int(value)
        elif unit.casefold().startswith("h"):
            hours += int(value)
        else:
            minutes += int(value)
    is_overdue = bool(re.search(r"retrasad|overdue|late", relative_text, re.IGNORECASE))
    return {
        "due_relative": relative_text,
        "relative_status": "OVERDUE" if is_overdue else "UPCOMING",
        "relative_hours": days * 24 + hours + (1 if minutes else 0),
    }


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def parse_submission_status(
    html: str,
    profile: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Detecta estados explícitos en la página de detalle de una entrega.

    Devuelve ``submitted=None`` si el HTML no contiene un estado reconocido. Esa
    diferencia evita presentar una actividad no inspeccionada como pendiente.
    """
    profile = profile or {}
    submission_config = profile.get("submission", {})
    indicators = submission_config.get("indicators", {})
    submitted_terms = tuple(
        _normalize(term) for term in indicators.get("submitted", DEFAULT_SUBMITTED_INDICATORS)
    )
    draft_terms = tuple(
        _normalize(term) for term in indicators.get("draft", DEFAULT_DRAFT_INDICATORS)
    )
    # Configurations predating explicit states may call drafts "pending". Check
    # draft markers separately and ignore the broad word "pending" so that
    # "submitted; pending grading" stays a submitted assignment.
    pending_terms = tuple(
        normalized
        for term in indicators.get("pending", DEFAULT_PENDING_INDICATORS)
        if (normalized := _normalize(term)) not in {"pendiente", "pending", *draft_terms}
    ) + tuple(_normalize(term) for term in DEFAULT_EMPTY_INDICATORS)
    soup = BeautifulSoup(html or "", "lxml")
    status_selectors = [
        submission_config.get("status_table", "table.generaltable"),
        ".submissionstatustable",
        "table",
    ]
    candidate_texts: List[str] = []
    seen_nodes = set()
    for selector in status_selectors:
        for table in soup.select(selector):
            if id(table) in seen_nodes:
                continue
            seen_nodes.add(id(table))
            for row in table.select("tr"):
                cells = row.find_all(["th", "td"], recursive=False)
                if len(cells) < 2:
                    cells = row.find_all(["th", "td"])
                if len(cells) < 2:
                    continue
                label = _normalize(cells[0].get_text(" ", strip=True))
                if any(word in label for word in ("estado de la entrega", "submission status")):
                    candidate_texts.append(cells[-1].get_text(" ", strip=True))
    candidate_texts.extend(
        node.get_text(" ", strip=True)
        for node in soup.select(".submissionstatus, [data-region='submission-status']")
    )

    for text in candidate_texts:
        normalized = _normalize(text)
        if any(term in normalized for term in draft_terms):
            return {"submitted": False, "state": "draft", "status_text": text}
        if any(term in normalized for term in pending_terms):
            return {"submitted": False, "state": "not_submitted", "status_text": text}
        if normalized in {"pendiente", "pending"}:
            return {"submitted": False, "state": "not_submitted", "status_text": text}
        if any(term in normalized for term in submitted_terms):
            return {"submitted": True, "state": "submitted", "status_text": text}
    return {
        "submitted": None,
        "state": "unknown",
        "status_text": "Estado de entrega no identificado",
    }


def filter_pending_assignments(
    assignments: Iterable[Dict[str, Any]],
    course_names: Iterable[str],
    today: Optional[date] = None,
    days_ahead: int = 7,
    days_behind: int = 7,
) -> List[Dict[str, Any]]:
    """Filtra entregas no enviadas por fecha absoluta o contador relativo de Moodle."""
    keywords = [_normalize(name).strip() for name in course_names if name and name.strip()]
    today = today or datetime.now().date()
    start = today - timedelta(days=max(days_behind, 0))
    end = today + timedelta(days=max(days_ahead, 0))
    pending: List[Dict[str, Any]] = []
    for assignment in assignments:
        course = _normalize(str(assignment.get("course", "")))
        submission = assignment.get("submission_status") or {}
        if keywords and not any(keyword in course for keyword in keywords):
            continue
        if submission.get("submitted") is not False:
            continue
        item = dict(assignment)
        if not item.get("due_date") and item.get("relative_status") in {"OVERDUE", "UPCOMING"}:
            relative_hours = int(item.get("relative_hours", 0))
            if item["relative_status"] == "OVERDUE":
                if relative_hours > max(days_behind, 0) * 24:
                    continue
                item["status"] = "OVERDUE"
                item["days_overdue"] = (relative_hours + 23) // 24
            else:
                if relative_hours > max(days_ahead, 0) * 24:
                    continue
                item["status"] = "UPCOMING"
                item["days_until_due"] = (relative_hours + 23) // 24
            pending.append(item)
            continue
        parsed = parse_date(assignment.get("due_date", ""))
        if not parsed:
            continue
        due = parsed.date() if isinstance(parsed, datetime) else parsed
        if not start <= due <= end:
            continue
        if due < today:
            item["status"] = "OVERDUE"
            item["days_overdue"] = (today - due).days
        elif due == today:
            item["status"] = "DUE_TODAY"
            item["days_until_due"] = 0
        else:
            item["status"] = "UPCOMING"
            item["days_until_due"] = (due - today).days
        pending.append(item)
    return pending
