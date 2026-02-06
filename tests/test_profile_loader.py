"""Tests para ProfileLoader y perfiles YAML."""
import pytest
from pathlib import Path

from lms_agent_scraper.core.profile_loader import ProfileLoader, PortalProfile


PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def test_list_profiles():
    loader = ProfileLoader(PROFILES_DIR)
    names = loader.list_profiles()
    assert "moodle_default" in names


def test_load_moodle_default():
    loader = ProfileLoader(PROFILES_DIR)
    profile = loader.load("moodle_default")
    assert isinstance(profile, PortalProfile)
    assert profile.metadata.get("lms_type") == "moodle"
    assert "form_selectors" in profile.auth
    assert profile.auth.get("form_selectors", {}).get("username") == "#username"
    assert profile.courses.get("selectors")
    assert profile.assignments.get("types")


def test_load_missing_profile_raises():
    loader = ProfileLoader(PROFILES_DIR)
    with pytest.raises(FileNotFoundError):
        loader.load("nonexistent_profile")


def test_get_assignment_selectors():
    loader = ProfileLoader(PROFILES_DIR)
    profile = loader.load("moodle_default")
    selectors = loader.get_assignment_selectors(profile)
    assert len(selectors) > 0
    assert any("assign" in s for s in selectors)
