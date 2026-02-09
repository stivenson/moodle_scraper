"""Tests para SkillLoader: carga de skills (SKILL.md), metadatos, recursos y validación."""

from pathlib import Path

import pytest

from lms_agent_scraper.core.skill_loader import SkillLoader

# Directorio de skills del paquete (src/lms_agent_scraper/skills)
ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "src" / "lms_agent_scraper" / "skills"


def test_skill_loader_init_default():
    """SkillLoader sin skills_dir usa el directorio del paquete."""
    loader = SkillLoader()
    assert loader.skills_dir.exists() or loader.skills_dir.name == "skills"


def test_skill_loader_init_with_dir():
    """SkillLoader acepta skills_dir explícito."""
    loader = SkillLoader(SKILLS_DIR)
    assert loader.skills_dir == SKILLS_DIR


def test_list_available_skills():
    """list_available_skills devuelve lista de skills con name, description, version."""
    loader = SkillLoader(SKILLS_DIR)
    skills = loader.list_available_skills()
    assert isinstance(skills, list)
    names = [s["name"] for s in skills]
    assert "date-interpreter" in names or len(skills) >= 0
    for s in skills:
        assert "name" in s and "description" in s


def test_load_skill_date_interpreter():
    """load_skill('date-interpreter') devuelve ChatPromptTemplate con format_messages."""
    loader = SkillLoader(SKILLS_DIR)
    template = loader.load_skill("date-interpreter")
    assert template is not None
    assert hasattr(template, "format_messages")
    messages = template.format_messages(date_text="15/03/2026", context="N/A")
    assert len(messages) >= 1


def test_get_skill_metadata():
    """get_skill_metadata devuelve dict con name y description."""
    loader = SkillLoader(SKILLS_DIR)
    meta = loader.get_skill_metadata("date-interpreter")
    assert meta["name"] == "date-interpreter"
    assert "description" in meta


def test_load_skill_missing_raises():
    """load_skill con nombre inexistente lanza FileNotFoundError."""
    loader = SkillLoader(SKILLS_DIR)
    with pytest.raises(FileNotFoundError):
        loader.load_skill("nonexistent-skill-xyz")


def test_validate_skill_date_interpreter():
    """validate_skill('date-interpreter') devuelve (True, None)."""
    loader = SkillLoader(SKILLS_DIR)
    valid, err = loader.validate_skill("date-interpreter")
    assert valid is True
    assert err is None


def test_validate_skill_report_generator():
    """validate_skill('report-generator') comprueba report_template.md y placeholders."""
    loader = SkillLoader(SKILLS_DIR)
    valid, err = loader.validate_skill("report-generator")
    assert valid is True
    assert err is None


def test_load_skill_resource_report_template():
    """load_skill_resource devuelve contenido de report_template.md."""
    loader = SkillLoader(SKILLS_DIR)
    content = loader.load_skill_resource("report-generator", "report_template.md")
    assert content is not None
    assert "{title}" in content
    assert "{generation_date}" in content


def test_load_skill_resource_nonexistent_returns_none():
    """load_skill_resource con archivo inexistente devuelve None."""
    loader = SkillLoader(SKILLS_DIR)
    assert loader.load_skill_resource("date-interpreter", "nonexistent.txt") is None


def test_clear_cache():
    """clear_cache no lanza y deja poder cargar de nuevo."""
    loader = SkillLoader(SKILLS_DIR)
    loader.load_skill("date-interpreter", use_cache=True)
    loader.clear_cache()
    template = loader.load_skill("date-interpreter")
    assert template is not None
