# 🐍 Entorno Virtual - Unisimon Scraper

**Requisito:** Python **3.10+**.

**Comando más sencillo (por defecto):** una vez activado el entorno, instalado el paquete (`pip install -e .`) y Playwright (`playwright install chromium`), y configurado `.env` desde `.env.example`, ejecuta:

```bash
python -m lms_agent_scraper.cli run
```

Usa los valores por defecto de `.env` (perfil, URL, credenciales, días). No requiere argumentos adicionales.

## 📁 Estructura del Proyecto

```
unisimon_scraper/
├── venv/                          # Entorno virtual (crear con: python -m venv venv)
├── activate_env.bat               # Script de activación (Windows)
├── .env.example                   # Plantilla de variables (v2 y legacy; copiar a .env)
├── validate_skills.py             # Valida prompts LLM (SKILL.md)
├── scraper.py                     # Scraper básico (legacy)
├── scraper_hybrid.py              # Scraper híbrido (legacy)
├── scraper_selenium.py            # Scraper con Selenium (legacy)
├── config.py                      # Lee desde .env para scripts legacy (mismas variables que v2)
├── utils.py                       # Utilidades legacy
├── requirements.txt               # Dependencias legacy
├── pyproject.toml                 # Paquete v2: pip install -e .
├── profiles/                      # Perfiles YAML por portal (v2)
├── src/lms_agent_scraper/         # LMS Agent Scraper v2 (CLI, MCP, workflow LangGraph)
│   ├── cli.py                     # Comandos: run, profiles list/validate
│   ├── agents/                    # login, course_discovery, analyzer
│   ├── graph/                     # Workflow LangGraph (nodes, state)
│   ├── llm/                       # Cliente Ollama
│   ├── tools/                     # browser_tools, extraction_tools, report_tools
│   ├── core/                      # profile_loader, skill_loader, date_parser
│   ├── skills/                    # Prompts LLM en SKILL.md (runtime)
│   └── mcp/                       # Servidor MCP
├── docs/
├── tests/
├── reports/                       # Reportes generados
└── debug_html/                    # HTML de debug (cuando SCRAPER_DEBUG_MODE=true)
```

## 🚀 Cómo usar el entorno virtual

### Opción 1: Usar el script de activación (Recomendado)
```bash
# Doble clic en el archivo o ejecutar desde terminal:
activate_env.bat
```

### Opción 2: Activación manual
```bash
# Activar el entorno virtual
venv\Scripts\activate

# Ejecutar el scraper (comando por defecto)
python -m lms_agent_scraper.cli run

# Desactivar el entorno
deactivate
```

## 📦 Dependencias

### Legacy (requirements.txt)

- **requests**, **beautifulsoup4**, **lxml** - HTTP y parsing HTML
- **selenium**, **webdriver-manager** - Automatización web (scraper_selenium, scraper_hybrid)
- **spacy** - Procesamiento de lenguaje natural (opcional)

### v2 – LMS Agent Scraper (pyproject.toml)

Instalación: `pip install -e .` (desde la raíz del repo). Incluye LangGraph, LangChain, Playwright, langchain-ollama, pydantic-settings, Typer, MCP, etc. Ver [pyproject.toml](pyproject.toml).

Para v2 además necesitas **Playwright** con Chromium:

```bash
playwright install chromium
```

## 🔧 Comandos Útiles

```bash
# Verificar que el entorno esté activo
where python

# Ver paquetes instalados
pip list

# Actualizar dependencias
pip install -r requirements.txt --upgrade

# Instalar nueva dependencia
pip install nombre_paquete

# Generar requirements.txt actualizado
pip freeze > requirements.txt
```

## 📊 Ejecutar el Scraper

Una vez activado el entorno virtual:

### v2 – LMS Agent Scraper (recomendado)

**Comando por defecto (el más sencillo):**

```bash
# 1. Instalar el paquete en modo editable (solo la primera vez)
pip install -e .

# 2. Instalar navegador para Playwright (solo la primera vez)
playwright install chromium

# 3. Configurar .env (copiar .env.example a .env; definir PORTAL_PROFILE, PORTAL_BASE_URL, PORTAL_USERNAME, PORTAL_PASSWORD)

# 4. Ejecutar (usa valores por defecto del .env)
python -m lms_agent_scraper.cli run
```

Otros comandos opcionales: `python -m lms_agent_scraper.cli run --profile moodle_unisimon`, `profiles list`, `profiles validate moodle_unisimon`.

### Legacy

```bash
# Scraper híbrido
python scraper_hybrid.py

# Scraper básico con BeautifulSoup
python scraper.py

# Scraper con Selenium completo
python scraper_selenium.py
```

### Otros

```bash
# Validar skills (prompts LLM en SKILL.md)
python validate_skills.py

# Depuración opcional del estado de entregas (legacy, scraper híbrido)
python debug_submissions.py
```

## 🐛 Solución de Problemas

### Error: "python no se reconoce como comando"
- Asegúrate de que el entorno virtual esté activado
- Verifica que Python esté instalado en el sistema

### Error: "ModuleNotFoundError"
- Activa el entorno virtual: `venv\Scripts\activate`
- Reinstala las dependencias: `pip install -r requirements.txt`

### Error de login en el scraper
- **v2 y legacy:** configura `PORTAL_BASE_URL`, `PORTAL_USERNAME` y `PORTAL_PASSWORD` en `.env`. `config.py` (legacy) también lee desde `.env`.
- Asegúrate de tener conexión a internet; el portal puede estar temporalmente fuera de servicio.

## 📝 Notas Importantes

- **Python 3.10+** requerido (v2 y recomendado para legacy).
- **Siempre activa el entorno virtual** antes de ejecutar el scraper.
- **v2:** las credenciales y la URL del portal van en `.env` (no versionado); ver `.env.example`.
- Los reportes se guardan en `reports/`; los archivos de debug (v2) en `debug_html/` cuando `SCRAPER_DEBUG_MODE=true`.
- El entorno virtual está aislado del sistema Python global.

---

*Entorno virtual para el proyecto Unisimon Portal Scraper / LMS Agent Scraper*
