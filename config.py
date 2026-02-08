# Configuration file for Unisimon Portal Scraper
# ================================================
# Carga valores desde .env (mismas variables que el flujo v2). Los scripts legacy
# (scraper.py, scraper_selenium.py, scraper_hybrid.py, debug_submissions.py) usan estas constantes.
# Uso recomendado: python -m lms_agent_scraper.cli run con .env configurado.

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def _env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip()

def _env_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except ValueError:
        return default

def _env_bool(key: str, default: bool) -> bool:
    v = os.environ.get(key, "").strip().lower()
    if v in ("1", "true", "yes"):
        return True
    if v in ("0", "false", "no"):
        return False
    return default

# TIME RANGE CONFIGURATION
# =========================
DAYS_AHEAD = _env_int("SCRAPER_DAYS_AHEAD", 7)
DAYS_BEHIND = _env_int("SCRAPER_DAYS_BEHIND", 7)

# LOGIN CREDENTIALS (desde .env: PORTAL_BASE_URL, PORTAL_LOGIN_PATH, PORTAL_USERNAME, PORTAL_PASSWORD)
# =================
_base = _env("PORTAL_BASE_URL", "https://example.edu").rstrip("/")
_path = _env("PORTAL_LOGIN_PATH", "/login/").strip() or "/login/"
LOGIN_URL = _base + (_path if _path.startswith("/") else "/" + _path)
USERNAME = _env("PORTAL_USERNAME", "your_username")
PASSWORD = _env("PORTAL_PASSWORD", "your_password")

# OUTPUT CONFIGURATION
# ====================
OUTPUT_DIR = _env("OUTPUT_DIR", "reports").strip() or "reports"
REPORT_FILENAME_PREFIX = "assignments_report"

# REQUEST CONFIGURATION
# =====================
REQUEST_TIMEOUT = _env_int("REQUEST_TIMEOUT", 30)
MAX_RETRIES = 3
RETRY_DELAY = 2

# USER AGENT
# ==========
USER_AGENT = _env(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
)

# DEBUG CONFIGURATION (SCRAPER_DEBUG_MODE, SCRAPER_SAVE_HTML_DEBUG en .env)
# ===================
DEBUG_MODE = _env_bool("SCRAPER_DEBUG_MODE", True)
SAVE_HTML_DEBUG = _env_bool("SCRAPER_SAVE_HTML_DEBUG", True)
