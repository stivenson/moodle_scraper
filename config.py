# Configuration file for Unisimon Portal Scraper
# ================================================
# No versionar credenciales reales. Usar placeholders aquí o copiar a config.local.py
# (y añadir config.local.py a .gitignore) para los scripts legacy (scraper.py, etc.).

# TIME RANGE CONFIGURATION
# =========================
# Number of days ahead to check for assignments
# Change this value to modify the time window for assignment checking
DAYS_AHEAD = 7  # Default: 7 days (1 week ahead)

# Number of days behind to check for overdue assignments
DAYS_BEHIND = 7  # Default: 7 days (1 week behind)

# LOGIN CREDENTIALS
# =================
LOGIN_URL = 'https://example.edu/login/'
USERNAME = 'your_username'
PASSWORD = 'your_password'

# OUTPUT CONFIGURATION
# ====================
OUTPUT_DIR = 'reports'
REPORT_FILENAME_PREFIX = 'assignments_report'

# REQUEST CONFIGURATION
# =====================
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# USER AGENT
# ==========
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# DEBUG CONFIGURATION
# ===================
DEBUG_MODE = True  # Set to False to reduce console output
SAVE_HTML_DEBUG = True  # Save HTML pages for debugging
