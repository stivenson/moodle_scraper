"""
Workflow principal del scraper como grafo LangGraph.
Flujo: Start -> Auth -> CourseDiscovery -> AssignmentExtractor -> DataProcessor -> ReportGenerator -> End
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from lms_agent_scraper.graph.state import ScraperState
from lms_agent_scraper.graph import nodes


def _normalize_base_url(url: str) -> str:
    """
    Normaliza la URL del portal al origen (scheme + netloc).
    Si el usuario pasa la URL completa del login (ej. .../login/index.php), se usa solo el origen
    para construir correctamente /my/courses.php y demás rutas.
    """
    if not url:
        return url
    parsed = urlparse(url.rstrip("/"))
    if not parsed.netloc:
        return url
    scheme = parsed.scheme or "https"
    return f"{scheme}://{parsed.netloc}"


log = logging.getLogger(__name__)

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = None


def build_workflow():
    """
    Construye y compila el grafo del scraper.
    """
    if not LANGGRAPH_AVAILABLE:
        raise RuntimeError("langgraph is not installed. pip install langgraph")

    workflow = StateGraph(ScraperState)

    workflow.add_node("authenticate", nodes.authentication_node)
    workflow.add_node("course_discovery", nodes.course_discovery_node)
    workflow.add_node("assignment_extractor", nodes.assignment_extractor_node)
    workflow.add_node("data_processor", nodes.data_processor_node)
    workflow.add_node("report_generator", nodes.report_generator_node)

    workflow.set_entry_point("authenticate")
    workflow.add_edge("authenticate", "course_discovery")
    workflow.add_edge("course_discovery", "assignment_extractor")
    workflow.add_edge("assignment_extractor", "data_processor")
    workflow.add_edge("data_processor", "report_generator")
    workflow.add_edge("report_generator", END)

    return workflow.compile()


def run_workflow(
    profile_name: str,
    base_url: str,
    username: str,
    password: str,
    days_ahead: int = 7,
    days_behind: int = 7,
    max_courses: int = 0,
    output_dir: str = "reports",
    profiles_dir: Optional[Path] = None,
    debug: bool = False,
) -> Dict[str, Any]:
    """
    Ejecuta el workflow: carga el perfil, construye estado inicial e invoca el grafo.
    """
    from lms_agent_scraper.core.profile_loader import ProfileLoader

    log.info("Workflow: cargando perfil '%s'...", profile_name)
    profiles_path = profiles_dir or Path("profiles")
    loader = ProfileLoader(profiles_path)
    profile_model = loader.load(profile_name)
    profile_dict = profile_model.model_dump()
    log.info(
        "Workflow: perfil cargado. Iniciando grafo (Auth -> Cursos -> Tareas -> Proceso -> Reporte)."
    )

    initial: ScraperState = {
        "profile_name": profile_name,
        "base_url": _normalize_base_url(base_url),
        "username": username,
        "password": password,
        "profile": profile_dict,
        "days_ahead": days_ahead,
        "days_behind": days_behind,
        "max_courses": max_courses,
        "output_dir": output_dir,
        "authenticated": False,
        "session_cookies": [],
        "courses": [],
        "assignments": [],
        "errors": [],
        "report_path": "",
        "_debug": debug,
    }

    graph = build_workflow()
    config = {"configurable": {}}
    final_state = graph.invoke(initial, config=config)
    log.info("Workflow: grafo finalizado.")
    return dict(final_state)
