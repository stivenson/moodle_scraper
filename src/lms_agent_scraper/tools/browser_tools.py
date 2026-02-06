"""
Herramientas de navegación con Playwright para login y obtención de cursos.
Incluye extracción por selectores (Playwright) y por parseo HTML (BeautifulSoup) como respaldo.
"""
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

log = logging.getLogger(__name__)

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


def _extract_courses_from_html(html: str, base_url: str, debug: bool = False) -> List[Dict[str, str]]:
    """
    Extrae la lista de cursos parseando el HTML con BeautifulSoup.
    Estrategias: tarjetas con data-region='course-content' o .course-card;
    nombre desde .coursename, span.multiline, texto del enlace o atributo title.
    """
    if not BS4_AVAILABLE:
        return []
    base_url = base_url.rstrip("/")
    soup = BeautifulSoup(html, "html.parser")
    seen_urls: set = set()
    course_list: List[Dict[str, str]] = []
    # Selectores de tarjeta de curso (Moodle block_myoverview / Unisimon)
    card_selectors = [
        "[data-region='course-content']",
        ".course-card",
        "div.card.course-card",
    ]
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
        # Fallback: cualquier enlace a course/view.php dentro de un contenedor tipo card/grid
        for container in soup.select("[data-region='courses-view'], .card-grid, .card-deck"):
            for a in container.find_all("a", href=re.compile(r"course/view\.php")):
                href = a.get("href")
                if not href or "course/view" not in href:
                    continue
                url = urljoin(base_url + "/", href)
                if url in seen_urls:
                    continue
                name = (a.get_text(strip=True) or "").strip()
                if not name and a.find_previous("span", class_=re.compile("multiline")):
                    name = a.find_previous("span", class_=re.compile("multiline")).get_text(strip=True)
                if len(name) >= 2:
                    seen_urls.add(url)
                    course_list.append({"url": url, "name": name or "Sin nombre"})
        return course_list
    for card in cards:
        link = card.find("a", href=re.compile(r"course/view\.php"))
        if not link:
            continue
        href = link.get("href")
        if not href:
            continue
        url = urljoin(base_url + "/", href)
        if url in seen_urls:
            continue
        # Nombre: prioridad coursename -> span.multiline -> title -> texto del enlace
        name = ""
        name_el = card.select_one("a.aalink.coursename, a.coursename, .coursename")
        if name_el:
            name = name_el.get_text(strip=True)
        if not name:
            mult = card.select_one("span.multiline")
            if mult:
                name = mult.get_text(strip=True) or mult.get("title", "")
        if not name and link:
            name = link.get_text(strip=True)
        if not name:
            title_el = card.select_one("[title]")
            if title_el:
                name = title_el.get("title", "")
        name = (name or "Sin nombre").strip()
        if len(name) >= 1:
            seen_urls.add(url)
            course_list.append({"url": url, "name": name})
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
            html_snapshot = page.content()
            log.info("  -> HTML de pagina de cursos: %d caracteres", len(html_snapshot or ""))
            if debug:
                from pathlib import Path
                debug_dir = Path("debug_html")
                debug_dir.mkdir(exist_ok=True)
                (debug_dir / "courses_page.html").write_text(html_snapshot, encoding="utf-8")
                log.debug("  [DEBUG] Saved courses_page.html")

            # Método principal: extraer cursos con LLM (Ollama) si está disponible
            course_list = _extract_courses_with_llm(html_snapshot, base_url, debug=debug)
            if course_list:
                log.info("  -> Cursos obtenidos con LLM (Ollama): %d", len(course_list))
                browser.close()
                return course_list
            log.info("  -> LLM no disponible o devolvio 0 cursos; probando selectores Playwright...")

            # Respaldo: locators de Playwright según el perfil
            seen_urls: set = set()
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
                        if href and "course/view" in href and len(text) >= 1:
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
                log.info("  -> Selectores Playwright: 0 enlaces; probando respaldo HTML (BeautifulSoup)...")

            # Respaldo: extraer desde el HTML parseado (BeautifulSoup)
            if not course_list and BS4_AVAILABLE:
                course_list = _extract_courses_from_html(html_snapshot, base_url, debug=debug)
                if course_list:
                    log.info("  -> Cursos obtenidos con respaldo HTML: %d", len(course_list))
                else:
                    log.warning("  -> Respaldo HTML: 0 cursos. Revisar selectores o que la pagina muestre 'Mis cursos'.")

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
