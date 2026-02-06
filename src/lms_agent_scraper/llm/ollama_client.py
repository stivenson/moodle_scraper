"""
Cliente Ollama para GLM-4.7-Flash: análisis de HTML, interpretación de fechas, sugerencia de selectores,
extracción de cursos desde la página "Mis cursos" (fallback con LLM).
"""
import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from lms_agent_scraper.config.ollama_config import OllamaSettings

try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    ChatOllama = None
    HumanMessage = None


class LocalLLMClient:
    """Cliente para inferencia local con GLM-4.7-Flash vía Ollama."""

    def __init__(self, settings: Optional[OllamaSettings] = None):
        self.settings = settings or OllamaSettings()
        self._llm = None
        if OLLAMA_AVAILABLE:
            try:
                self._llm = ChatOllama(
                    model=self.settings.model_name,
                    base_url=self.settings.base_url,
                    temperature=self.settings.temperature,
                    num_ctx=self.settings.num_ctx,
                    num_predict=self.settings.num_predict,
                )
            except Exception:
                self._llm = None

    @property
    def available(self) -> bool:
        return OLLAMA_AVAILABLE and self._llm is not None

    def _invoke(self, prompt: str) -> str:
        if not self._llm:
            return ""
        try:
            response = self._llm.invoke([HumanMessage(content=prompt)])
            return (response.content or "").strip()
        except Exception:
            return ""

    def analyze_html_structure(self, html: str, max_chars: int = 4000) -> Dict[str, str]:
        """
        Analiza un fragmento HTML y sugiere selectores CSS para tareas/assignments (estilo Moodle).
        Retorna dict con assignment_selector, date_selector (o vacío si falla).
        """
        if not self.available:
            return {}
        snippet = html[:max_chars] if html else ""
        prompt = f"""Analiza el siguiente HTML y propón selectores CSS para:
1) Enlaces a tareas/assignments (assignment_selector)
2) Elementos que muestran fecha de entrega (date_selector)

Responde ÚNICAMENTE con un JSON válido, sin markdown, con exactamente estas claves:
{{"assignment_selector": "selector_css", "date_selector": "selector_css"}}

HTML:
{snippet}
"""
        out = self._invoke(prompt)
        if not out:
            return {}
        # Limpiar posible markdown
        out = re.sub(r"^```\w*\n?", "", out)
        out = re.sub(r"\n?```\s*$", "", out)
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {}

    def interpret_date(self, date_text: str, context: str = "") -> str:
        """
        Interpreta una fecha ambigua y devuelve ISO (YYYY-MM-DD).
        """
        if not self.available or not date_text:
            return ""
        prompt = f"""Fecha encontrada: "{date_text}"
Contexto: {context[:500] if context else 'N/A'}

Convierte a formato ISO (YYYY-MM-DD). Responde SOLO con la fecha en formato ISO, nada más."""
        out = self._invoke(prompt)
        if not out:
            return ""
        # Extraer primer patrón YYYY-MM-DD
        m = re.search(r"\d{4}-\d{2}-\d{2}", out)
        return m.group(0) if m else ""

    def suggest_selectors_on_error(self, error_message: str, html_snippet: str = "") -> Dict[str, str]:
        """
        Dado un mensaje de error de scraping y opcionalmente un fragmento HTML,
        sugiere nuevos selectores para reintentar.
        """
        if not self.available:
            return {}
        prompt = f"""Error durante el scraping: {error_message}
{f'Fragmento HTML: {html_snippet[:3000]}' if html_snippet else ''}

Sugiere selectores CSS alternativos para encontrar enlaces a tareas/assignments en un LMS tipo Moodle.
Responde ÚNICAMENTE con JSON: {{"assignment_selector": "...", "date_selector": "..."}}
"""
        out = self._invoke(prompt)
        out = re.sub(r"^```\w*\n?", "", out)
        out = re.sub(r"\n?```\s*$", "", out)
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return {}

    def extract_courses_from_html(
        self, html: str, base_url: str, max_chars: int = 18000
    ) -> List[Dict[str, str]]:
        """
        Usa el LLM para extraer la lista de cursos desde el HTML de la página "Mis cursos" (Moodle).
        Útil cuando los selectores y BeautifulSoup no encuentran tarjetas.
        base_url: para normalizar URLs relativas (ej. https://aulapregrado.unisimon.edu.co).
        Retorna lista de dicts con "name" y "url".
        """
        if not self.available or not html:
            return []
        base_url = base_url.rstrip("/")
        # Reducir HTML: quitar scripts y estilos para meter más contenido útil en el contexto
        snippet = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        snippet = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", snippet, flags=re.IGNORECASE)
        snippet = snippet[:max_chars] if len(snippet) > max_chars else snippet
        prompt = f"""El siguiente HTML corresponde a la página "Mis cursos" de un campus Moodle (Aula Pregrado).
Tu tarea: extraer TODOS los cursos listados. Para cada curso necesito:
1) El nombre completo del curso (tal como aparece en pantalla).
2) La URL del curso. Debe contener "course/view.php" y el parámetro "id" (ej: course/view.php?id=3418).
   Si la URL es relativa (empieza con / o sin dominio), considérala relativa al sitio.

Responde ÚNICAMENTE con un JSON válido: un array de objetos, cada uno con exactamente dos claves "name" y "url".
Ejemplo: [{{"name": "CUC ALGEBRA LINEAL - 2795 - T01 - 2026 - 1", "url": "https://aulapregrado.unisimon.edu.co/course/view.php?id=3418"}}]
No incluyas explicaciones ni markdown. Solo el array JSON.

HTML:
{snippet}
"""
        out = self._invoke(prompt)
        if not out:
            return []
        out = re.sub(r"^```\w*\n?", "", out)
        out = re.sub(r"\n?```\s*$", "", out)
        out = out.strip()
        try:
            raw = json.loads(out)
        except json.JSONDecodeError:
            return []
        if not isinstance(raw, list):
            return []
        result: List[Dict[str, str]] = []
        seen: set = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = (item.get("name") or "").strip()
            url = (item.get("url") or "").strip()
            if not url or "course/view" not in url:
                continue
            url = urljoin(base_url + "/", url)
            if url in seen:
                continue
            seen.add(url)
            result.append({"url": url, "name": name or "Sin nombre"})
        return result
