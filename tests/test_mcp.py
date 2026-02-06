"""Tests para el servidor MCP (herramientas disponibles y list_profiles)."""
from pathlib import Path

import pytest

# Importar después de conftest que añade src al path
from lms_agent_scraper.mcp.server import list_profiles

PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def test_list_profiles_tool_returns_string():
    # list_profiles es una herramienta MCP; al llamarla debe devolver string
    result = list_profiles()
    assert isinstance(result, str)
    # Si existe el directorio profiles con moodle_default, debe aparecer
    if PROFILES_DIR.exists():
        assert "moodle_default" in result or "No hay" in result
