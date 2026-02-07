"""
Herramientas de navegación con Playwright para login y obtención de cursos.
Incluye extracción por selectores (Playwright) y por parseo HTML (BeautifulSoup) como respaldo.
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

log = logging.getLogger(__name__)

# Defaults tipo Moodle para extracción de cursos (usados cuando el perfil no define card_selectors, etc.)
DEFAULT_CARD_SELECTORS = [
    "[data-region='course-content']",
    ".course-card",
    "div.card.course-card",
]
DEFAULT_NAME_SELECTORS = [
    "a.aalink.coursename",
    "a.coursename",
    ".coursename",
    "span.multiline",
    "[title]",
]
DEFAULT_LINK_HREF_PATTERN = "course/view"
DEFAULT_FALLBACK_CONTAINERS = [
    "[data-region='courses-view']",
    ".card-grid",
    ".card-deck",
]

# Palabras clave para detectar enlaces a curso por segmento del path (case-insensitive).
# Si algún segmento del path de la URL contiene alguna de estas palabras, se considera enlace a curso.
DEFAULT_COURSE_LINK_SEGMENTS = ["course", "courses", "cursos"]


def _is_course_url_by_segment(
    href: str,
    base_url: str,
    segment_keywords: List[str],
) -> bool:
    """
    Indica si el href es un enlace a curso según segmentos del path.
    Un enlace es de curso si algún segmento del path contiene alguna de las palabras
    en segment_keywords (comparación case-insensitive).
    """
    if not href or not segment_keywords:
        return False
    base_url = base_url.rstrip("/")
    try:
        full_url = urljoin(base_url + "/", href)
        parsed = urlparse(full_url)
        path = (parsed.path or "").strip("/")
    except Exception:
        return False
    segments = [s.lower() for s in path.split("/") if s]
    keywords_lower = [k.lower() for k in segment_keywords if k]
    for seg in segments:
        for kw in keywords_lower:
            if kw in seg:
                return True
    return False


def _get_course_link_segments_from_profile(courses_profile: Optional[Dict[str, Any]]) -> List[str]:
    """
    Obtiene la lista de palabras clave para detectar enlaces a curso desde el perfil.
    Soporta course_link_segments (lista) o course_link_segment (singular); si no hay nada, usa default.
    """
    profile = courses_profile or {}
    if "course_link_segments" in profile and profile["course_link_segments"]:
        segments = profile["course_link_segments"]
        return segments if isinstance(segments, list) else [str(segments)]
    if "course_link_segment" in profile and profile["course_link_segment"]:
        return [str(profile["course_link_segment"])]
    return list(DEFAULT_COURSE_LINK_SEGMENTS)


def detect_more_navigation(
    page: Any,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Detecta si la página tiene controles de "más navegación" (Ver más, Siguiente, etc.).
    config: dict con selectors (lista de selectores CSS o texto), opcional expand_before_extract, max_clicks.
    Retorna has_more, control_type, element_count.
    """
    if not PLAYWRIGHT_AVAILABLE or not config:
        return {"has_more": False, "control_type": None, "element_count": 0}
    selectors = config.get("selectors") or []
    for sel in selectors:
        try:
            count = page.locator(sel).count()
            if count > 0:
                control_type = "button" if "button" in sel.lower() else "link"
                return {"has_more": True, "control_type": control_type, "element_count": count}
        except Exception:
            continue
    return {"has_more": False, "control_type": None, "element_count": 0}


def _expand_more_navigation(
    page: Any,
    config: Dict[str, Any],
    max_wait_ms: int = 2000,
) -> None:
    """Hace click en controles de 'más navegación' hasta max_clicks veces."""
    selectors = config.get("selectors") or []
    max_clicks = config.get("max_clicks", 0)
    if max_clicks <= 0 or not selectors:
        return
    for _ in range(max_clicks):
        clicked = False
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=3000)
                    clicked = True
                    time.sleep(min(max_wait_ms / 1000, 1.5))
                    break
            except Exception:
                continue
        if not clicked:
            break


def detect_courses_presence(html: str, courses_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Detecta si en el HTML hay tarjetas de curso (sin extraer nombres/URLs).
    Usa card_selectors del perfil o defaults Moodle.
    Retorna dict con has_courses, card_count, selector_matched.
    """
    if not BS4_AVAILABLE or not html:
        return {"has_courses": False, "card_count": 0, "selector_matched": None}
    profile = courses_profile or {}
    card_selectors = profile.get("card_selectors") or DEFAULT_CARD_SELECTORS
    soup = BeautifulSoup(html, "html.parser")
    for sel in card_selectors:
        try:
            nodes = soup.select(sel)
            if nodes:
                return {
                    "has_courses": True,
                    "card_count": len(nodes),
                    "selector_matched": sel,
                }
        except Exception:
            continue
    return {"has_courses": False, "card_count": 0, "selector_matched": None}


try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    BeautifulSoup = None

try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None


def login_with_playwright(
    base_url: str,
    username: str,
    password: str,
    auth_profile: Dict[str, Any],
    login_path: str = "/login/",
    headless: bool = True,
    timeout_ms: int = 15000,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Autentica en el portal usando Playwright y el perfil de auth (selectores).
    Retorna dict con success, cookies (lista de dicts name/value/domain), error (opcional).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "success": False,
            "cookies": [],
            "error": "playwright not installed. pip install playwright && playwright install chromium",
        }

    login_url = f"{base_url.rstrip('/')}{login_path}"
    form = auth_profile.get("form_selectors", {})
    username_sel = form.get("username", "#username")
    password_sel = form.get("password", "#password")
    submit_sel = form.get("submit", "#loginbtn")
    success_indicators = auth_profile.get("success_indicators", [])
    error_indicators = auth_profile.get("error_indicators", [])

    result: Dict[str, Any] = {"success": False, "cookies": [], "error": None}

    try:
        log.info("  -> Navegando a pagina de login...")
        with sync_playwright() as p:
            browser: Browser = p.chromium.launch(headless=headless)
            context: BrowserContext = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page: Page = context.new_page()

            page.goto(login_url, wait_until="domcontentloaded", timeout=timeout_ms)
            if debug:
                print(f"[DEBUG] Navigated to {login_url}")

            log.info("  -> Enviando credenciales y esperando redireccion...")
            page.wait_for_selector(username_sel, timeout=timeout_ms)
            page.fill(username_sel, username)
            page.fill(password_sel, password)
            page.click(submit_sel)

            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            time.sleep(2)
            current_url = page.url
            if debug:
                print(f"[DEBUG] After submit: {current_url}")

            # Check success indicators
            success = False
            for ind in success_indicators:
                if isinstance(ind, dict):
                    if "url_contains" in ind and ind["url_contains"] in current_url:
                        success = True
                        break
                    if "element_present" in ind:
                        try:
                            page.wait_for_selector(ind["element_present"], timeout=5000)
                            success = True
                            break
                        except PlaywrightTimeout:
                            pass

            # Check error indicators
            if not success:
                for ind in error_indicators:
                    if isinstance(ind, dict):
                        if "text_contains" in ind:
                            content = page.content()
                            if ind["text_contains"].lower() in content.lower():
                                result["error"] = f"Login failed: page contains '{ind['text_contains']}'"
                                break
                        if "element_present" in ind:
                            try:
                                if page.locator(ind["element_present"]).count() > 0:
                                    result["error"] = "Login failed: error element present"
                                    break
                            except Exception:
                                pass

            if success:
                cookies = context.cookies()
                result["success"] = True
                result["cookies"] = [
                    {"name": c["name"], "value": c["value"], "domain": c.get("domain", "")}
                    for c in cookies
                ]
            elif result.get("error") is None:
                result["error"] = f"Login failed: redirected to {current_url}"

            browser.close()
    except PlaywrightTimeout as e:
        result["error"] = f"Timeout: {e}"
    except Exception as e:
        result["error"] = str(e)

    return result


def _extract_courses_from_html(
    html: str,
    base_url: str,
    courses_profile: Optional[Dict[str, Any]] = None,
    debug: bool = False,
) -> List[Dict[str, str]]:
    """
    Extrae la lista de cursos parseando el HTML con BeautifulSoup.
    Si se pasa courses_profile, usa card_selectors, name_selectors, link_selector,
    link_href_pattern y fallback_containers del perfil; si no, usa defaults Moodle.
    """
    if not BS4_AVAILABLE:
        return []
    base_url = base_url.rstrip("/")
    profile = courses_profile or {}
    card_selectors = profile.get("card_selectors") or DEFAULT_CARD_SELECTORS
    name_selectors = profile.get("name_selectors") or DEFAULT_NAME_SELECTORS
    link_selector = profile.get("link_selector")
    link_href_pattern = profile.get("link_href_pattern") or DEFAULT_LINK_HREF_PATTERN
    fallback_containers = profile.get("fallback_containers") or DEFAULT_FALLBACK_CONTAINERS

    href_re = re.compile(re.escape(link_href_pattern) if link_href_pattern else "course/view")
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set = set()
    course_list: List[Dict[str, str]] = []

    cards = []
    for sel in card_selectors:
        try:
            cards = soup.select(sel)
            if cards:
                if debug:
                    log.debug("  [HTML] Found %d cards with %s", len(cards), sel)
                break
        except Exception:
            continue

    if not cards:
        # Fallback: enlaces dentro de contenedores del perfil
        for container_sel in fallback_containers:
            for container in soup.select(container_sel):
                for a in container.find_all("a", href=True):
                    href = a.get("href") or ""
                    if not href_re.search(href):
                        continue
                    url = urljoin(base_url + "/", href)
                    if url in seen_urls:
                        continue
                    name = (a.get_text(strip=True) or "").strip()
                    if not name:
                        prev = a.find_previous("span", class_=re.compile("multiline"))
                        if prev:
                            name = prev.get_text(strip=True) or prev.get("title", "")
                    if len(name) >= 2 or (len(name) >= 1 and len(url) >= 10):
                        seen_urls.add(url)
                        course_list.append({"url": url, "name": name or "Sin nombre"})
        return course_list

    for card in cards:
        if link_selector:
            link = card.select_one(link_selector)
        else:
            link = card.find("a", href=href_re)
        if not link or not link.get("href"):
            continue
        href = link.get("href", "")
        if not href_re.search(href):
            continue
        url = urljoin(base_url + "/", href)
        if url in seen_urls:
            continue
        name = ""
        for ns in name_selectors:
            try:
                name_el = card.select_one(ns)
                if name_el:
                    name = name_el.get_text(strip=True) or name_el.get("title", "") or ""
                    if name:
                        break
            except Exception:
                continue
        if not name and link:
            name = link.get_text(strip=True) or ""
        if not name:
            title_el = card.select_one("[title]")
            if title_el:
                name = title_el.get("title", "") or ""
        name = (name or "Sin nombre").strip()
        if len(name) >= 1:
            seen_urls.add(url)
            course_list.append({"url": url, "name": name})
    return course_list




def _extract_courses_by_link_segment(
    html: str,
    base_url: str,
    courses_profile: Optional[Dict[str, Any]] = None,
    debug: bool = False,
) -> List[Dict[str, str]]:
    """
    Extrae cursos buscando todos los enlaces cuya URL tenga en algún segmento del path
    una de las palabras clave configuradas (p. ej. course, courses, cursos). No depende de CSS.
    """
    if not BS4_AVAILABLE or not html:
        return []
    base_url = base_url.rstrip("/")
    segment_keywords = _get_course_link_segments_from_profile(courses_profile)
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set = set()
    course_list: List[Dict[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        if not _is_course_url_by_segment(href, base_url, segment_keywords):
            continue
        url = urljoin(base_url + "/", href)
        if url in seen_urls:
            continue
        name = (a.get_text(strip=True) or "").strip()
        if len(name) >= 2 or (len(name) >= 1 and len(url) >= 10):
            seen_urls.add(url)
            course_list.append({"url": url, "name": name or "Sin nombre"})
    if debug and course_list:
        log.debug("  [link_segment] Encontrados %d cursos por segmento URL (keywords: %s)", len(course_list), segment_keywords)
    return course_list


def _extract_courses_with_llm(html: str, base_url: str, debug: bool = False) -> List[Dict[str, str]]:
    """
    Usa el LLM local (Ollama / GLM-4.7-Flash) para extraer cursos desde el HTML de "Mis cursos".
    Es el método principal cuando Ollama está disponible; si no hay cursos, se usa Playwright y BeautifulSoup como respaldo.
    """
    try:
        from lms_agent_scraper.llm.ollama_client import LocalLLMClient
        client = LocalLLMClient()
        if not client.available:
            if debug:
                log.debug("  [DEBUG] Ollama no disponible; omitiendo extraccion con LLM")
            return []
        return client.extract_courses_from_html(html, base_url, max_chars=18000)
    except Exception as e:
        if debug:
            log.debug("  [DEBUG] LLM extraction error: %s", e)
        return []


def get_course_links_with_playwright(
    base_url: str,
    navigation_profile: Dict[str, Any],
    courses_profile: Dict[str, Any],
    cookies: List[Dict[str, Any]],
    headless: bool = True,
    timeout_ms: int = 20000,
    debug: bool = False,
    course_discovery_profile: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Obtiene la lista de cursos desde la página de cursos usando Playwright y cookies de sesión.
    Si course_discovery_profile tiene fallback_when_empty: true y no se encontraron cursos,
    se usa el agente de descubrimiento por contenido (visitar enlaces y clasificar con LLM).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []

    courses_page_path = navigation_profile.get("courses_page", "/my/courses.php")
    courses_url = f"{base_url.rstrip('/')}{courses_page_path}"
    container_sel = courses_profile.get("container", "[data-region='courses-view']")
    selectors = courses_profile.get("selectors", ["a[href*='course/view.php']"])
    link_href_pattern = courses_profile.get("link_href_pattern") or DEFAULT_LINK_HREF_PATTERN

    course_list: List[Dict[str, str]] = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            if cookies:
                context.add_cookies(
                    [
                        {
                            "name": c["name"],
                            "value": c["value"],
                            "domain": c.get("domain", "").lstrip(".") or base_url.replace("https://", "").split("/")[0],
                            "path": "/",
                        }
                        for c in cookies
                    ]
                )
            page = context.new_page()
            log.info("  -> Navegando a pagina de cursos (%s)...", courses_page_path)
            page.goto(courses_url, wait_until="domcontentloaded", timeout=timeout_ms)
            # Dar tiempo al JS (block_myoverview): networkidle y luego esperar tarjetas
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            try:
                page.wait_for_selector("[data-region='course-content']", timeout=12000)
            except Exception:
                try:
                    page.wait_for_selector(".course-card", timeout=6000)
                except Exception:
                    if debug:
                        log.debug("  [DEBUG] No course cards selector, continuing")
            time.sleep(1)

            # Opcional: expandir "Ver más" / paginación antes de capturar HTML
            more_nav = courses_profile.get("more_navigation") or {}
            if more_nav.get("expand_before_extract") and more_nav.get("selectors"):
                _expand_more_navigation(page, more_nav)

            html_snapshot = page.content()
            log.info("  -> HTML de pagina de cursos: %d caracteres", len(html_snapshot or ""))
            if debug:
                from pathlib import Path
                debug_dir = Path("debug_html")
                debug_dir.mkdir(exist_ok=True)
                (debug_dir / "courses_page.html").write_text(html_snapshot, encoding="utf-8")
                log.debug("  [DEBUG] Saved courses_page.html")

            # Detección explícita de presencia de tarjetas de curso
            presence = detect_courses_presence(html_snapshot, courses_profile)
            log.info(
                "  -> Presencia de cursos: has_courses=%s, card_count=%d, selector=%s",
                presence["has_courses"],
                presence["card_count"],
                presence.get("selector_matched") or "n/a",
            )

            # 0) Extracción por segmento de URL (palabras clave: course, courses, cursos, etc.)
            segment_keywords = _get_course_link_segments_from_profile(courses_profile)
            course_list = _extract_courses_by_link_segment(
                html_snapshot, base_url, courses_profile=courses_profile, debug=debug
            )
            if course_list:
                log.info(
                    "  -> Cursos obtenidos por enlaces (segmento URL, keywords=%s): %d",
                    segment_keywords,
                    len(course_list),
                )
                browser.close()
                return course_list

            # 1) Extracción con BeautifulSoup (selectores del perfil o defaults Moodle)
            if BS4_AVAILABLE:
                course_list = _extract_courses_from_html(
                    html_snapshot, base_url, courses_profile=courses_profile, debug=debug
                )
                if course_list:
                    log.info("  -> Cursos obtenidos con HTML (BeautifulSoup): %d", len(course_list))
                    browser.close()
                    return course_list
            log.info("  -> BeautifulSoup: 0 cursos; probando LLM...")

            # 2) LLM (Ollama) si está disponible
            course_list = _extract_courses_with_llm(html_snapshot, base_url, debug=debug)
            if course_list:
                log.info("  -> Cursos obtenidos con LLM (Ollama): %d", len(course_list))
                browser.close()
                return course_list
            log.info("  -> LLM no disponible o devolvio 0; probando selectores Playwright...")

            # 3) Playwright: primero todos los enlaces filtrados por segmento URL, luego selectores CSS
            seen_urls: set = set()
            segment_keywords_playwright = _get_course_link_segments_from_profile(courses_profile)
            try:
                for link_el in page.locator("a[href]").all():
                    try:
                        href = link_el.get_attribute("href")
                        if not href:
                            continue
                        if not _is_course_url_by_segment(href, base_url, segment_keywords_playwright):
                            continue
                        url = urljoin(base_url + "/", href)
                        if url in seen_urls:
                            continue
                        text = (link_el.inner_text() or "").strip()
                        if len(text) >= 2 or (len(text) >= 1 and len(url) >= 10):
                            seen_urls.add(url)
                            course_list.append({"url": url, "name": text or "Sin nombre"})
                    except Exception:
                        continue
            except Exception:
                pass
            if course_list:
                log.info(
                    "  -> Cursos obtenidos con Playwright (enlaces por segmento URL): %d",
                    len(course_list),
                )
            else:
                # 3b) Selectores CSS del perfil
                scope = page
                try:
                    if page.locator(container_sel).count() > 0:
                        scope = page.locator(container_sel).first
                except Exception:
                    pass
                for sel in selectors:
                    links = scope.locator(sel).all()
                    for link in links:
                        try:
                            href = link.get_attribute("href")
                            text = (link.inner_text() or "").strip()
                            if href and link_href_pattern in href and len(text) >= 1:
                                url = urljoin(base_url + "/", href)
                                if url not in seen_urls:
                                    seen_urls.add(url)
                                    course_list.append({"url": url, "name": text.strip()})
                        except Exception:
                            continue
                    if course_list:
                        break
                if course_list:
                    log.info("  -> Cursos obtenidos con selectores Playwright: %d", len(course_list))
                else:
                    log.info("  -> Selectores Playwright: 0 enlaces.")

            if presence["has_courses"] and not course_list:
                log.warning(
                    "  -> La pagina tiene %d tarjeta(s) de curso pero la extraccion devolvio 0. Revisar selectores del perfil.",
                    presence["card_count"],
                )

            # Fallback: descubrimiento por contenido (visitar enlaces y clasificar con LLM)
            if not course_list and course_discovery_profile and course_discovery_profile.get("fallback_when_empty"):
                from lms_agent_scraper.agents.course_discovery_agent import discover_courses_by_visiting_links
                log.info("  -> Ejecutando discovery por contenido (visitar enlaces + LLM)...")
                course_list = discover_courses_by_visiting_links(
                    page=page,
                    base_url=base_url,
                    html_current_page=html_snapshot,
                    discovery_config=course_discovery_profile,
                    timeout_ms=min(timeout_ms, 15000),
                    debug=debug,
                )
                if course_list:
                    log.info("  -> Cursos obtenidos con discovery por contenido: %d", len(course_list))

            browser.close()
    except Exception as e:
        if debug:
            print(f"[DEBUG] get_course_links error: {e}")

    return course_list
