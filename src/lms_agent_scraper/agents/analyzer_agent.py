"""
Agente de análisis con LLM local (GLM-4.7-Flash): manejo de errores y sugerencia de selectores.

API futura: este módulo no está referenciado por el workflow actual. Está preparado para uso
en un nodo de reintento (p. ej. tras fallos de extracción) que use run_error_analysis o para
interpretación de fechas ambiguas con interpret_dates_with_llm. No eliminar sin consenso.
"""

from typing import Any, Dict, List

from lms_agent_scraper.graph.state import ScraperState
from lms_agent_scraper.llm.ollama_client import LocalLLMClient


def run_error_analysis(state: ScraperState) -> Dict[str, Any]:
    """
    Analiza los errores del estado y, si hay LLM disponible, sugiere correcciones
    (p. ej. nuevos selectores o interpretación de fechas).

    API futura: no usada por el workflow actual; prevista para un nodo de reintento.
    """
    errors = state.get("errors", [])
    if not errors:
        return {"suggested_selectors": {}, "suggestion_message": ""}

    client = LocalLLMClient()
    if not client.available:
        return {
            "suggested_selectors": {},
            "suggestion_message": "Ollama no disponible; instalar y ejecutar ollama run glm-4.7-flash:q4_K_M",
        }

    combined_error = "; ".join(errors[-3:])  # Últimos 3 errores
    suggested = client.suggest_selectors_on_error(combined_error, html_snippet="")
    if suggested:
        return {
            "suggested_selectors": suggested,
            "suggestion_message": f"Probar selectores: {suggested}",
        }
    return {"suggested_selectors": {}, "suggestion_message": ""}


def interpret_dates_with_llm(
    date_strings: List[str],
    context: str = "",
) -> Dict[str, str]:
    """
    Interpreta una lista de cadenas de fecha ambiguas con el LLM y devuelve mapa fecha_original -> ISO.

    API futura: no usada por el workflow actual; prevista para enriquecer el date_parser.
    """
    client = LocalLLMClient()
    if not client.available:
        return {}
    result = {}
    for d in date_strings:
        if d and d not in result:
            iso = client.interpret_date(d, context)
            if iso:
                result[d] = iso
    return result
