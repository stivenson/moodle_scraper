"""Pytest fixtures and path setup."""
import sys
from pathlib import Path

# Asegurar que src está en el path
root = Path(__file__).resolve().parent.parent
src = root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

# Directorio de perfiles para tests
PROFILES_DIR = root / "profiles"


def pytest_configure(config):
    """Registrar marcadores si hace falta."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
