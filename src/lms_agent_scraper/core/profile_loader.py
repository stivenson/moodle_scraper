"""Carga y validación de perfiles YAML de portales LMS."""

from pathlib import Path
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel


class PortalProfile(BaseModel):
    """Perfil completo de un portal LMS."""

    metadata: Dict[str, str]
    auth: Dict[str, Any]
    navigation: Dict[str, str]
    courses: Dict[str, Any]
    assignments: Dict[str, Any]
    dates: Dict[str, Any]
    submission: Dict[str, Any]
    sections: Dict[str, Any]
    reports: Dict[str, Any]


class ProfileLoader:
    """Carga y valida perfiles YAML de portales."""

    def __init__(self, profiles_dir: Path | str = None):
        self.profiles_dir = Path(profiles_dir or "profiles")
        self._cache: Dict[str, PortalProfile] = {}

    def load(self, profile_name: str) -> PortalProfile:
        """Carga un perfil por nombre (con cache)."""
        if profile_name in self._cache:
            return self._cache[profile_name]

        profile_path = self.profiles_dir / f"{profile_name}.yml"
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile not found: {profile_path}")

        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError(f"Profile file is empty: {profile_path}")

        profile = PortalProfile(**data)
        self._cache[profile_name] = profile
        return profile

    def list_profiles(self) -> List[str]:
        """Lista perfiles disponibles."""
        if not self.profiles_dir.exists():
            return []
        return sorted(p.stem for p in self.profiles_dir.glob("*.yml"))

    def get_assignment_selectors(self, profile: PortalProfile) -> List[str]:
        """Obtiene todos los selectores de assignments del perfil."""
        selectors = []
        for atype in profile.assignments.get("types", []):
            selectors.extend(atype.get("selectors", []))
        return selectors
