"""
Agente de autenticación: login en el portal usando perfil YAML y Playwright.

API futura: el workflow actual usa directamente nodes.authentication_node -> login_with_playwright.
Este módulo expone run_auth y create_auth_runner como API programática alternativa (misma
implementación en browser_tools). Útil para tests o para inyectar un auth_runner custom.
No eliminar sin consenso.
"""

from typing import Any, Dict, Optional

from lms_agent_scraper.core.profile_loader import ProfileLoader, PortalProfile
from lms_agent_scraper.tools.browser_tools import login_with_playwright


def run_auth(
    profile: PortalProfile,
    base_url: str,
    username: str,
    password: str,
    login_path: Optional[str] = None,
    headless: bool = True,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Ejecuta login en el portal usando el perfil de auth y Playwright.
    Retorna dict con success, cookies, error (para inyectar en ScraperState._auth_result).

    API futura: no usada por el workflow actual; uso programático o tests.
    """
    auth = profile.auth
    path = login_path or auth.get("login_path", "/login/")
    result = login_with_playwright(
        base_url=base_url,
        username=username,
        password=password,
        auth_profile=auth,
        login_path=path,
        headless=headless,
        debug=debug,
    )
    return result


def create_auth_runner(
    profile_name: str,
    profiles_dir: str = "profiles",
    headless: bool = True,
    debug: bool = False,
):
    """
    Factory: retorna un callable (base_url, username, password) -> auth_result
    para usar con run_workflow(..., auth_runner=...) cuando se soporte inyección.

    API futura: no usada por el workflow actual; prevista para dependency inversion.
    """
    loader = ProfileLoader(profiles_dir)
    profile = loader.load(profile_name)

    def runner(*, base_url: str, username: str, password: str) -> Dict[str, Any]:
        return run_auth(profile, base_url, username, password, headless=headless, debug=debug)

    return runner
