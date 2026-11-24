# 🐍 Entorno virtual — LMS Agent Scraper (Moodle)

**Requisito:** Python **3.10+**.

**Comando más sencillo (por defecto):** una vez activado el entorno, instalado el paquete (`pip install -e .`) y Playwright (`playwright install chromium`), y configurado `.env` desde `.env.example`, ejecuta:

```bash
python -m lms_agent_scraper.cli run
```

Usa los valores por defecto de `.env` (perfil, URL, credenciales, días). No requiere argumentos adicionales.

## 📁 Estructura del Proyecto

```
moodle_scraper/
├── venv/                          # Entorno virtual (crear con: python -m venv venv)
├── activate_env.bat               # Script de activación (Windows)
├── .env.example                   # Plantilla de variables (copiar a .env)
├── validate_skills.py              # Valida prompts LLM (SKILL.md)
├── pyproject.toml                 # Paquete: pip install -e .
├── profiles/                      # Perfiles YAML por portal
├── src/lms_agent_scraper/         # LMS Agent Scraper (CLI, MCP, workflow LangGraph)
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

Instalación: `pip install -e .` (desde la raíz del repo). Incluye LangGraph, LangChain, Playwright, langchain-ollama, pydantic-settings, Typer, MCP, etc. Ver [pyproject.toml](pyproject.toml).

Además necesitas **Playwright** con Chromium:

```bash
playwright install chromium
```

## 🔧 Comandos Útiles

```bash
# Verificar que el entorno esté activo
where python

# Ver paquetes instalados
pip list

# Actualizar el paquete en modo editable
pip install -e .

# Instalar nueva dependencia (añadir al pyproject.toml si es del proyecto)
pip install nombre_paquete
```

## 📊 Ejecutar el Scraper

Una vez activado el entorno virtual:

**Comando por defecto (el más sencillo):**

```bash
# 1. Instalar el paquete en modo editable (solo la primera vez)
pip install -e .

# 2. Instalar navegador para Playwright (solo la primera vez)
playwright install chromium

# 3. Configurar .env (copiar .env.example a .env; definir PORTAL_PROFILE, PORTAL_BASE_URL, PORTAL_USERNAME, PORTAL_PASSWORD). La plantilla usa moodle_default y una URL Moodle ficticia; moodle_unisimon es un adaptador opcional para Aula Extendida. SCRAPER_TARGET_COURSES permite filtrar cursos separados por coma; vacío incluye todos los cursos descubiertos.

# 4. Ejecutar (usa valores por defecto del .env)
python -m lms_agent_scraper.cli run
```

Otros comandos opcionales: `python -m lms_agent_scraper.cli run --profile moodle_unisimon` (perfil de ejemplo, Unisimon), `profiles list`, `profiles validate moodle_unisimon`.

**Validar skills (prompts LLM en SKILL.md):**

```bash
python validate_skills.py
```

## 🐛 Solución de Problemas

### Error: "python no se reconoce como comando"
- Asegúrate de que el entorno virtual esté activado
- Verifica que Python esté instalado en el sistema

### Error: "ModuleNotFoundError"
- Activa el entorno virtual: `venv\Scripts\activate`
- Reinstala el paquete: `pip install -e .`

### Error de login en el scraper
- Configura `PORTAL_BASE_URL`, `PORTAL_USERNAME` y `PORTAL_PASSWORD` en `.env`.
- Asegúrate de tener conexión a internet; el portal puede estar temporalmente fuera de servicio.

## 📝 Notas Importantes

- **Comando recomendado:** `python -m lms_agent_scraper.cli run` (usa valores de `.env`).
- **MCP:** `get_pending_assignments` acepta cursos configurados; `read_assignment` lee tareas descubiertas y `manage_submission` gestiona las entregas propias. Las acciones que cambian entregas requieren `confirmed=true` y validación del estado actual.
- **Python 3.10+** requerido.
- **Siempre activa el entorno virtual** antes de ejecutar el scraper.
- Las credenciales y la URL del portal van en `.env` (no versionado); ver `.env.example`.
- Los reportes se guardan en `reports/`; los archivos de debug (v2) en `debug_html/` cuando `SCRAPER_DEBUG_MODE=true`.
- El entorno virtual está aislado del sistema Python global.

---

*Entorno virtual para el sistema de scrapers IA para Moodle (LMS Agent Scraper)*
