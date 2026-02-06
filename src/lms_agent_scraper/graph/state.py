"""Definición del estado del grafo LangGraph para el scraper."""
from typing import Any, Dict, List, TypedDict


class ScraperState(TypedDict, total=False):
    """Estado compartido del workflow del scraper."""

    authenticated: bool
    session_cookies: List[Dict[str, Any]]
    courses: List[Dict[str, Any]]
    assignments: List[Dict[str, Any]]
    errors: List[str]
    report_path: str
    profile_name: str
    base_url: str
    username: str
    password: str
    profile: Dict[str, Any]
    # Parámetros de ejecución
    days_ahead: int
    days_behind: int
    max_courses: int
    output_dir: str
