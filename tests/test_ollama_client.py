"""Tests para LocalLLMClient (ollama_client). Sin invocar Ollama; comprueba comportamiento cuando no está disponible."""

from pathlib import Path


from lms_agent_scraper.llm.ollama_client import LocalLLMClient, _default_skills_dir


def test_default_skills_dir():
    """_default_skills_dir apunta al directorio skills del paquete."""
    d = _default_skills_dir()
    assert d.is_dir() or not d.exists()
    assert "skills" in str(d).replace("\\", "/")


def test_client_creation_without_settings():
    """LocalLLMClient se crea sin settings (usa defaults)."""
    client = LocalLLMClient()
    assert client.settings is not None
    assert client._skills_dir is not None


def test_client_creation_with_skills_dir():
    """LocalLLMClient acepta skills_dir opcional."""
    custom = Path("custom_skills_xyz")
    client = LocalLLMClient(skills_dir=custom)
    assert client._skills_dir == custom


def test_analyze_html_structure_when_not_available_returns_empty():
    """Sin LLM disponible, analyze_html_structure devuelve dict vacío."""
    client = LocalLLMClient()
    # Si Ollama no está corriendo, available será False
    result = client.analyze_html_structure("<html><body>test</body></html>")
    assert isinstance(result, dict)
    # Puede estar vacío o tener claves si el LLM respondió; sin LLM debe estar vacío
    if not client.available:
        assert result == {}


def test_interpret_date_when_not_available_returns_empty():
    """Sin LLM disponible o con fecha vacía, interpret_date devuelve cadena vacía."""
    client = LocalLLMClient()
    if not client.available:
        assert client.interpret_date("15/03/2026") == ""
    assert client.interpret_date("") == ""


def test_suggest_selectors_on_error_when_not_available_returns_empty():
    """Sin LLM disponible, suggest_selectors_on_error devuelve dict vacío."""
    client = LocalLLMClient()
    result = client.suggest_selectors_on_error("Error de selector", "<div>html</div>")
    assert isinstance(result, dict)
    if not client.available:
        assert result == {}


def test_extract_courses_from_html_when_not_available_returns_empty():
    """Sin LLM disponible o HTML vacío, extract_courses_from_html devuelve lista vacía."""
    client = LocalLLMClient()
    if not client.available:
        assert client.extract_courses_from_html("<html></html>", "https://example.edu") == []
    assert client.extract_courses_from_html("", "https://example.edu") == []


def test_classify_page_as_course_when_not_available_returns_default():
    """Sin LLM disponible o HTML vacío, classify_page_as_course devuelve is_course=False."""
    client = LocalLLMClient()
    default = {"is_course": False, "course_name": ""}
    if not client.available:
        assert client.classify_page_as_course("<html></html>") == default
    assert client.classify_page_as_course("") == default


def test_extract_assignments_from_course_html_when_not_available_returns_empty():
    """Sin LLM disponible o HTML vacío, extract_assignments_from_course_html devuelve lista vacía."""
    client = LocalLLMClient()
    if not client.available:
        assert (
            client.extract_assignments_from_course_html(
                "<html></html>", "Curso", "https://example.edu"
            )
            == []
        )
    assert client.extract_assignments_from_course_html("", "Curso", "https://example.edu") == []
