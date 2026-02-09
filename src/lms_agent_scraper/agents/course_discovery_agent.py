"""
Agente de descubrimiento de cursos por contenido: extrae enlaces candidatos de la página actual,
visita cada uno con Playwright y clasifica con el LLM si el contenido es una página de curso.
"""

import logging
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

from lms_agent_scraper.llm.ollama_client import LocalLLMClient

log = logging.getLogger(__name__)

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup = None

# Page type from Playwright for type hints; avoid import at top so module loads without playwright
try:
    from playwright.sync_api import Page
except ImportError:
    Page = None  # type: ignore[misc, assignment]


DEFAULT_CANDIDATE_PATTERNS = ["course/view.php", "/course/"]
EXCLUDE_PATH_SUBSTRINGS = ["/login", "logout", "/admin", "login.php", "logout.php"]


def _extract_candidate_urls(
    html: str,
    base_url: str,
    candidate_patterns: List[str],
    max_candidates: int,
    debug: bool = False,
) -> List[str]:
    """
    Extrae URLs candidatas del HTML: mismo dominio, href que coincida con algún patrón,
    excluyendo login/logout/admin. Deduplica y limita a max_candidates.
    """
    if not BS4_AVAILABLE or not html:
        return []
    base_url = base_url.rstrip("/")
    base_host = urlparse(base_url).netloc.lower()
    soup = BeautifulSoup(html, "html.parser")
    seen: set = set()
    candidates: List[str] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        full_url = urljoin(base_url + "/", href)
        try:
            parsed = urlparse(full_url)
        except Exception:
            continue
        if parsed.netloc.lower() != base_host:
            continue
        path_lower = (parsed.path or "").lower()
        if any(exc in path_lower or exc in full_url.lower() for exc in EXCLUDE_PATH_SUBSTRINGS):
            continue
        if not any(pat in full_url for pat in candidate_patterns):
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        candidates.append(full_url)
        if len(candidates) >= max_candidates:
            break
    if debug:
        log.debug("  [course_discovery_agent] Candidatos extraidos: %d", len(candidates))
    return candidates


def discover_courses_by_visiting_links(
    page: Any,
    base_url: str,
    html_current_page: str,
    discovery_config: Dict[str, Any],
    timeout_ms: int = 15000,
    debug: bool = False,
) -> List[Dict[str, str]]:
    """
    Descubre cursos visitando enlaces candidatos de la página actual y clasificando
    el contenido de cada destino con el LLM (Ollama). Usa el mismo `page` de Playwright
    (con cookies ya inyectadas).

    discovery_config puede contener:
      - fallback_when_empty: no se usa aquí (lo usa quien invoca).
      - max_candidates: máximo de URLs a visitar (default 25).
      - candidate_patterns: lista de subcadenas para filtrar href (default course/view.php, /course/).

    Retorna lista de {"url": str, "name": str}.
    """
    max_candidates = int(discovery_config.get("max_candidates", 25))
    candidate_patterns = discovery_config.get("candidate_patterns") or DEFAULT_CANDIDATE_PATTERNS

    candidates = _extract_candidate_urls(
        html_current_page,
        base_url,
        candidate_patterns,
        max_candidates,
        debug=debug,
    )
    log.info("  -> Discovery por contenido: %d enlace(s) candidato(s) extraidos", len(candidates))
    if not candidates:
        return []

    client = LocalLLMClient()
    if not client.available:
        log.warning("  -> Discovery por contenido: Ollama no disponible, omitiendo.")
        return []

    course_list: List[Dict[str, str]] = []
    visited = 0
    for url in candidates:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            html = page.content()
            visited += 1
            result = client.classify_page_as_course(html, url=url, max_chars=8000)
            if result.get("is_course"):
                name = (result.get("course_name") or "").strip() or "Sin nombre"
                course_list.append({"url": url, "name": name})
                log.info("  -> Discovery por contenido: curso detectado [%s] %s", name[:50], url)
        except Exception as e:
            if debug:
                log.debug("  [course_discovery_agent] Error visitando %s: %s", url, e)
            continue
    log.info(
        "  -> Discovery por contenido: visitadas %d pagina(s), %d curso(s) detectado(s)",
        visited,
        len(course_list),
    )
    return course_list
