"""
Herramientas de extracción de tareas desde HTML usando perfil de selectores.
"""
import logging
import time
from typing import Any, Dict, List, Optional

import requests

log = logging.getLogger(__name__)
from bs4 import BeautifulSoup

from lms_agent_scraper.core.date_parser import parse_date, extract_date_from_text


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def session_from_cookies(
    cookies: List[Dict[str, Any]],
    base_url: str,
) -> requests.Session:
    """Crea una sesión requests con las cookies de sesión del portal."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    })
    domain = base_url.replace("https://", "").replace("http://", "").split("/")[0]
    for c in cookies:
        name = c.get("name")
        value = c.get("value")
        dom = c.get("domain", "").lstrip(".") or domain
        if name and value:
            session.cookies.set(name, value, domain=dom)
    return session


def _assignment_type_from_href(href: str, profile_types: List[Dict]) -> str:
    """Determina el tipo de actividad desde la URL según el perfil."""
    href_lower = (href or "").lower()
    for atype in profile_types or []:
        for sel in atype.get("selectors", []):
            if "assign" in sel and "assign" in href_lower:
                return atype.get("name", "assignment")
            if "quiz" in sel and "quiz" in href_lower:
                return "quiz"
            if "forum" in sel and "forum" in href_lower:
                return "forum"
            if "workshop" in sel and "workshop" in href_lower:
                return "workshop"
    if "assign" in href_lower:
        return "assignment"
    if "quiz" in href_lower:
        return "quiz"
    if "forum" in href_lower:
        return "forum"
    return "activity"


def extract_assignments_from_html(
    html: str,
    course_name: str,
    course_url: str,
    profile: Dict[str, Any],
    section_name: str = "Main",
    base_url: str = "",
) -> List[Dict[str, Any]]:
    """
    Extrae lista de assignments desde el HTML de una página de curso
    usando los selectores del perfil.
    """
    soup = BeautifulSoup(html, "lxml")
    assignments = []
    assignment_selectors = []
    for atype in profile.get("assignments", {}).get("types", []):
        assignment_selectors.extend(atype.get("selectors", []))

    date_config = profile.get("dates", {})
    date_selectors = date_config.get("selectors", [])
    date_patterns = date_config.get("patterns", [])

    seen_hrefs = set()
    for selector in assignment_selectors:
        for link in soup.select(selector):
            try:
                href = link.get("href", "")
                if not href or href in seen_hrefs:
                    continue
                title = link.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                seen_hrefs.add(href)
                if base_url and not href.startswith("http"):
                    href = base_url.rstrip("/") + ("/" if not href.startswith("/") else "") + href
                due_date_str = ""
                parent = link.parent
                if parent:
                    parent_text = parent.get_text(strip=True)
                    due_date_str = extract_date_from_text(parent_text, date_patterns) or ""
                    if not due_date_str:
                        for ds in date_selectors:
                            elem = parent.select_one(ds)
                            if elem:
                                due_date_str = elem.get_text(strip=True)
                                break
                assignment_type = _assignment_type_from_href(
                    href,
                    profile.get("assignments", {}).get("types", []),
                )
                assignments.append({
                    "title": title,
                    "due_date": due_date_str or "",
                    "course": course_name,
                    "type": assignment_type,
                    "url": href,
                    "section": section_name,
                    "submission_status": {"submitted": False, "status_text": "No entregada"},
                    "attached_files": [],
                })
            except Exception:
                continue
    return assignments


def get_assignments_for_courses(
    courses: List[Dict[str, str]],
    cookies: List[Dict[str, Any]],
    profile: Dict[str, Any],
    base_url: str,
    max_courses: int = 0,
    timeout: int = 30,
) -> List[Dict[str, Any]]:
    """
    Por cada curso, obtiene la página y extrae assignments.
    Retorna la lista agregada de assignments.
    """
    if not courses:
        return []
    session = session_from_cookies(cookies, base_url)
    all_assignments = []
    limit = len(courses) if max_courses <= 0 else min(max_courses, len(courses))
    for i, course in enumerate(courses[:limit]):
        course_url = course.get("url", "")
        course_name = course.get("name", "Sin nombre")
        if not course_url:
            continue
        log.info("  → Curso %d/%d: %s", i + 1, limit, course_name[:50] + ("..." if len(course_name) > 50 else ""))
        if not course_url.startswith("http"):
            course_url = base_url.rstrip("/") + ("/" if not course_url.startswith("/") else "") + course_url
        try:
            resp = session.get(course_url, timeout=timeout)
            resp.raise_for_status()
            items = extract_assignments_from_html(
                resp.text,
                course_name=course_name,
                course_url=course_url,
                profile=profile,
                section_name="Main",
                base_url=base_url,
            )
            all_assignments.extend(items)
        except Exception:
            continue
        time.sleep(0.5)
    return all_assignments
