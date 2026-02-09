"""
Cliente Ollama para GLM-4.7-Flash: análisis de HTML, interpretación de fechas, sugerencia de selectores,
extracción de cursos desde la página "Mis cursos" (fallback con LLM).
Soporta prompts desde SKILL.md (skills_dir) con fallback a prompts hardcodeados.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from lms_agent_scraper.config.ollama_config import OllamaSettings

logger = logging.getLogger(__name__)

try:
    from langchain_ollama import ChatOllama
    from langchain_core.messages import HumanMessage

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    ChatOllama = None
    HumanMessage = None


def _default_skills_dir() -> Path:
    """Directorio por defecto de skills (package_root/skills)."""
    return Path(__file__).resolve().parent.parent / "skills"


class LocalLLMClient:
    """Cliente para inferencia local con GLM-4.7-Flash vía Ollama."""

    def __init__(
        self,
        settings: Optional[OllamaSettings] = None,
        skills_dir: Optional[Path] = None,
    ):
        self.settings = settings or OllamaSettings()
        self._skills_dir = Path(skills_dir) if skills_dir is not None else _default_skills_dir()
        self._skill_loader = None
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
            out = (response.content or "").strip()
            logger.info("Respuesta del modelo: %s", out[:2000] + ("..." if len(out) > 2000 else ""))
            return out
        except Exception:
            return ""

    def _strip_markdown_and_parse_json(self, out: str) -> Optional[Any]:
        """Quita bloques markdown del texto y parsea JSON. Retorna None si falla."""
        if not out:
            return None
        out = re.sub(r"^```\w*\n?", "", out)
        out = re.sub(r"\n?```\s*$", "", out)
        out = out.strip()
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            return None

    def _get_skill_loader(self):
        """Lazy init del SkillLoader si skills_dir existe."""
        if self._skill_loader is not None:
            return self._skill_loader
        if not self._skills_dir.exists():
            return None
        try:
            from lms_agent_scraper.core.skill_loader import SkillLoader

            self._skill_loader = SkillLoader(self._skills_dir)
            return self._skill_loader
        except Exception as e:
            logger.debug("SkillLoader no disponible: %s", e)
            return None

    def _prompt_from_skill(self, skill_name: str, **kwargs: Any) -> Optional[str]:
        """Construye el prompt desde un skill (SKILL.md). Retorna None si falla."""
        loader = self._get_skill_loader()
        if loader is None:
            return None
        try:
            template = loader.load_skill(skill_name)
            messages = template.format_messages(**kwargs)
            parts = [getattr(m, "content", str(m)) for m in messages]
            return "\n\n".join(p for p in parts if p)
        except Exception as e:
            logger.debug("Prompt desde skill %s no disponible: %s", skill_name, e)
            return None

    def analyze_html_structure(self, html: str, max_chars: int = 4000) -> Dict[str, str]:
        """
        Analiza un fragmento HTML y sugiere selectores CSS para tareas/assignments (estilo Moodle).
        Retorna dict con assignment_selector, date_selector (o vacío si falla).
        """
        if not self.available:
            return {}
        snippet = html[:max_chars] if html else ""
        prompt = self._prompt_from_skill("html-structure-analyzer", snippet=snippet)
        if prompt is None:
            prompt = f"""Analiza el siguiente HTML y propón selectores CSS para:
1) Enlaces a tareas/assignments (assignment_selector)
2) Elementos que muestran fecha de entrega (date_selector)

Responde ÚNICAMENTE con un JSON válido, sin markdown, con exactamente estas claves:
{{"assignment_selector": "selector_css", "date_selector": "selector_css"}}

HTML:
{snippet}
"""
        out = self._invoke(prompt)
        parsed = self._strip_markdown_and_parse_json(out)
        return parsed if isinstance(parsed, dict) else {}

    def interpret_date(self, date_text: str, context: str = "") -> str:
        """
        Interpreta una fecha ambigua y devuelve ISO (YYYY-MM-DD).
        """
        if not self.available or not date_text:
            return ""
        prompt = self._prompt_from_skill(
            "date-interpreter",
            date_text=date_text,
            context=context[:500] if context else "N/A",
        )
        if prompt is None:
            prompt = f"""Fecha encontrada: "{date_text}"
Contexto: {context[:500] if context else "N/A"}

Convierte a formato ISO (YYYY-MM-DD). Responde SOLO con la fecha en formato ISO, nada más."""
        out = self._invoke(prompt)
        if not out:
            return ""
        # Extraer primer patrón YYYY-MM-DD
        m = re.search(r"\d{4}-\d{2}-\d{2}", out)
        return m.group(0) if m else ""

    def suggest_selectors_on_error(
        self, error_message: str, html_snippet: str = ""
    ) -> Dict[str, str]:
        """
        Dado un mensaje de error de scraping y opcionalmente un fragmento HTML,
        sugiere nuevos selectores para reintentar.
        """
        if not self.available:
            return {}
        prompt = self._prompt_from_skill(
            "selector-suggester",
            error_message=error_message,
            html_snippet=html_snippet[:3000] if html_snippet else "",
        )
        if prompt is None:
            prompt = f"""Error durante el scraping: {error_message}
{f"Fragmento HTML: {html_snippet[:3000]}" if html_snippet else ""}

Sugiere selectores CSS alternativos para encontrar enlaces a tareas/assignments en un LMS tipo Moodle.
Responde ÚNICAMENTE con JSON: {{"assignment_selector": "...", "date_selector": "..."}}
"""
        out = self._invoke(prompt)
        parsed = self._strip_markdown_and_parse_json(out)
        return parsed if isinstance(parsed, dict) else {}

    def _run_course_extractor(
        self, html: str, base_url: str, max_chars: int = 18000
    ) -> List[Dict[str, str]]:
        """
        Dominio: extracción de cursos desde HTML "Mis cursos". Construye prompt, invoca LLM y parsea.
        """
        base_url = base_url.rstrip("/")
        snippet = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        snippet = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", snippet, flags=re.IGNORECASE)
        snippet = snippet[:max_chars] if len(snippet) > max_chars else snippet
        prompt = self._prompt_from_skill(
            "course-extractor",
            snippet=snippet,
            base_url=base_url,
        )
        if prompt is None:
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
        raw = self._strip_markdown_and_parse_json(out)
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
        return self._run_course_extractor(html, base_url, max_chars=max_chars)

    def _run_page_classifier(
        self, html: str, url: str = "", max_chars: int = 8000
    ) -> Dict[str, Any]:
        """
        Dominio: clasificación de página como curso. Construye prompt, invoca LLM y parsea.
        """
        snippet = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        snippet = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", snippet, flags=re.IGNORECASE)
        snippet = snippet[:max_chars] if len(snippet) > max_chars else snippet
        prompt = self._prompt_from_skill(
            "course-page-classifier",
            snippet=snippet,
            url=url or "",
        )
        if prompt is None:
            url_hint = f"\nURL de la página: {url}" if url else ""
            prompt = f"""El siguiente HTML es de un sitio LMS tipo Moodle (ej. Aula Pregrado).
Determina si esta página es una PÁGINA DE CURSO (vista principal de un curso), no una lista de cursos ni el dashboard.

Señales de página de curso:
- Título del curso (h1, .course-header, .page-header, o similar).
- Secciones o módulos del curso (temas, semanas).
- Enlaces a actividades: mod/assign, mod/quiz, mod/forum, tareas, foros, cuestionarios.
- Navegación típica de curso (pestañas, bloques laterales de curso).

Si es solo una lista de cursos, el dashboard, login o una página genérica, NO es página de curso.
{url_hint}

Responde ÚNICAMENTE con un JSON válido, sin markdown, con exactamente estas claves:
{{"is_course": true o false, "course_name": "nombre del curso tal como aparece en la página o vacío si no es curso"}}

HTML:
{snippet}
"""
        out = self._invoke(prompt)
        data = self._strip_markdown_and_parse_json(out)
        if not isinstance(data, dict):
            return {"is_course": False, "course_name": ""}
        is_course = bool(data.get("is_course", False))
        course_name = (data.get("course_name") or "").strip()
        return {"is_course": is_course, "course_name": course_name}

    def classify_page_as_course(
        self, html: str, url: str = "", max_chars: int = 8000
    ) -> Dict[str, Any]:
        """
        Clasifica si el HTML corresponde a una página de curso en un LMS tipo Moodle.
        Busca señales: título del curso, secciones/módulos, enlaces a actividades (assign, quiz, forum).
        Retorna {"is_course": bool, "course_name": str}. course_name vacío si no es curso.
        """
        default = {"is_course": False, "course_name": ""}
        if not self.available or not html:
            return default
        return self._run_page_classifier(html, url=url, max_chars=max_chars)

    def extract_assignments_from_course_html(
        self,
        html: str,
        course_name: str,
        base_url: str,
        max_chars: int = 18000,
    ) -> List[Dict[str, Any]]:
        """
        Usa el LLM para extraer tareas/entregas desde el HTML de la página de un curso (Moodle).
        Retorna lista de dicts en formato estándar del pipeline: title, due_date, course, type,
        url, section, submission_status, attached_files.
        """
        if not self.available or not html:
            return []
        base_url = base_url.rstrip("/")
        snippet = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        snippet = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", snippet, flags=re.IGNORECASE)
        snippet = snippet[:max_chars] if len(snippet) > max_chars else snippet
        prompt = self._prompt_from_skill(
            "assignment-extractor",
            snippet=snippet,
            course_name=course_name or "Curso",
            base_url=base_url,
        )
        if prompt is None:
            prompt = f"""El siguiente HTML es la página principal de un curso en un LMS tipo Moodle (Aula Pregrado).
Curso: {course_name or "Curso"}
Base URL del sitio: {base_url}

Tu tarea: identificar TODAS las tareas, entregas, actividades evaluables (tareas, entregas, cuestionarios, foros de entrega, talleres, etc.), aunque la redacción sea diversa. Para cada una extrae:
1) title: título tal como aparece.
2) due_date: fecha de entrega o vencimiento si está visible (texto o formato coherente); si no hay, cadena vacía "".
3) url: URL del enlace a la actividad (absoluta o relativa al sitio). Debe contener mod/assign, mod/quiz, mod/forum o mod/workshop.
4) type: uno de assignment, quiz, forum, workshop.

Responde ÚNICAMENTE con un JSON válido: un array de objetos con exactamente las claves "title", "due_date", "url", "type".
Ejemplo: [{{"title": "Tarea 1", "due_date": "15/03/2026", "url": "/mod/assign/view.php?id=123", "type": "assignment"}}]
No incluyas explicaciones ni markdown. Solo el array JSON.

HTML:
{snippet}
"""
        out = self._invoke(prompt)
        raw = self._strip_markdown_and_parse_json(out)
        if not isinstance(raw, list):
            return []
        result: List[Dict[str, Any]] = []
        seen_urls: set = set()
        valid_types = {"assignment", "quiz", "forum", "workshop"}
        for item in raw:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            if not title:
                continue
            url = (item.get("url") or "").strip()
            if not url or (
                "mod/" not in url
                and "assign" not in url
                and "quiz" not in url
                and "forum" not in url
                and "workshop" not in url
            ):
                continue
            url = urljoin(base_url + "/", url)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            raw_type = (item.get("type") or "assignment").strip().lower()
            activity_type = raw_type if raw_type in valid_types else "assignment"
            due_date_str = (item.get("due_date") or "").strip()
            result.append(
                {
                    "title": title,
                    "due_date": due_date_str,
                    "course": course_name or "Sin nombre",
                    "type": activity_type,
                    "url": url,
                    "section": "Main",
                    "submission_status": {"submitted": False, "status_text": "No entregada"},
                    "attached_files": [],
                }
            )
        return result
