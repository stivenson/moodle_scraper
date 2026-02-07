# Unisimon Portal Scraper / LMS Agent Scraper

Un scraper automatizado para extraer tareas pendientes del portal de Unisimon Aula Pregrado.

**Versión 2 (LMS Agent Scraper):** Framework generalizado con LangGraph, perfiles YAML, MCP y soporte para múltiples portales LMS. Ver sección "Uso LMS Agent Scraper (v2)" más abajo.

## 🚀 Características

- ✅ Autenticación automática en el portal (Playwright)
- 📅 Filtrado de tareas por período personalizable (días adelante/atrás)
- 📊 Generación de reportes en formato Markdown
- 🔍 Modo debug para análisis del portal
- 🛠️ **v2:** Workflow LangGraph (auth → discovery → extracción → reporte), perfiles YAML, MCP
- 🛠️ **v2:** Detección de cursos: BeautifulSoup (principal), LLM (Ollama) y Playwright como respaldo; detección de presencia de tarjetas; fallback por contenido (visitar enlaces y clasificar con LLM)
- 🛠️ Scripts legacy: `scraper.py`, `scraper_selenium.py`, `scraper_hybrid.py` para uso sin el paquete v2

## 📁 Estructura del Proyecto

```
unisimon_scraper/
├── scraper.py              # Script principal (legacy)
├── scraper_selenium.py     # Alternativa con Selenium (legacy)
├── scraper_hybrid.py       # Híbrido (legacy)
├── config.py               # Configuración legacy
├── utils.py                # Utilidades legacy
├── requirements.txt
├── pyproject.toml          # Paquete instalable (v2)
├── .env.example            # Plantilla de variables para v2
├── profiles/               # Perfiles YAML por portal (v2)
│   ├── moodle_unisimon.yml
│   ├── moodle_default.yml
│   └── ...
├── src/lms_agent_scraper/  # LMS Agent Scraper (v2)
│   ├── cli.py              # Comandos: run, profiles list/validate
│   ├── agents/             # Agentes (login, course discovery, analyzer)
│   ├── graph/              # Workflow LangGraph (nodes, workflow, state)
│   ├── llm/                # Cliente Ollama (extracción y clasificación)
│   ├── tools/              # browser_tools, extraction_tools, report_tools
│   ├── core/               # date_parser, profile_loader, skill_loader
│   ├── skills/             # Prompts LLM en SKILL.md (date-interpreter, course-extractor, etc.)
│   └── mcp/                # Servidor MCP
├── validate_skills.py      # Valida que los skills (SKILL.md) carguen correctamente
├── .agents/skills/        # Skills de skills.sh (agent-browser, pdf, webapp-testing, etc.)
├── docs/
│   ├── AGENT_SKILLS.md
│   ├── ARCHITECTURE_VERIFICATION.md
│   └── SOLID_AND_QUALITY.md
├── tests/
└── reports/                # Reportes Markdown generados
```

## ⚙️ Configuración

### 1. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 2. Configurar Credenciales

Edita `config.py` y actualiza las siguientes constantes:

```python
# Credenciales de acceso
USERNAME = 'tu_usuario'
PASSWORD = 'tu_contraseña'

# Período de consulta (en días)
DAYS_AHEAD = 21  # Cambia este valor para modificar el período
```

### 3. Personalizar Configuración

Puedes modificar estas constantes en `config.py`:

- `DAYS_AHEAD`: Número de días hacia adelante para buscar tareas (por defecto: 21 días)
- `REQUEST_TIMEOUT`: Timeout para las peticiones HTTP (por defecto: 30 segundos)
- `DEBUG_MODE`: Activar/desactivar mensajes de debug
- `SAVE_HTML_DEBUG`: Guardar páginas HTML para análisis

## 🎯 Uso

### Ejecución Básica

```bash
python scraper.py
```

### Salida

El script generará:

1. **Reporte Markdown**: `reports/assignments_report_YYYYMMDD_HHMMSS.md`
2. **Archivos de Debug** (si está habilitado): `debug_html/`
3. **Mensajes en consola** con el progreso y resultados

## 📊 Formato del Reporte

El reporte incluye:

- 📅 Fecha de generación y período consultado
- 📖 Tareas agrupadas por curso
- ⏰ Fechas de entrega con indicadores de urgencia
- 📝 Descripciones y requisitos de cada tarea
- 🔢 Conteo total de tareas encontradas

## 🔧 Solución de Problemas

### Error de Autenticación

Si el login falla:

1. Verifica las credenciales en `config.py`
2. Comprueba que la URL del portal sea correcta
3. Revisa los archivos HTML de debug en `debug_html/`

### No se Encuentran Tareas

Si no se encuentran tareas:

1. **Portal con JavaScript**: El portal podría usar JavaScript para cargar contenido dinámicamente
2. **Estructura cambiada**: El portal podría haber cambiado su estructura HTML
3. **Sin tareas**: Realmente no hay tareas en el período consultado
4. **v2 / Unisimon**: Si usas el scraper v2 con Unisimon Aula Pregrado, pon `PORTAL_PROFILE=moodle_unisimon` en `.env`. Con `moodle_default` puede que no se detecten las tarjetas de curso. Para depurar: `SCRAPER_DEBUG_MODE=true` y revisar `debug_html/courses_page.html`.

### Migración a Selenium

Si BeautifulSoup no es suficiente (contenido JavaScript), sigue estos pasos:

#### 1. Instalar Selenium

```bash
pip install selenium
```

#### 2. Instalar Driver del Navegador

**Para Chrome:**
```bash
# Descargar ChromeDriver desde: https://chromedriver.chromium.org/
# O usar webdriver-manager:
pip install webdriver-manager
```

#### 3. Crear `scraper_selenium.py`

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

class UnisimonSeleniumScraper:
    def __init__(self):
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service)
        self.driver.implicitly_wait(10)
    
    def login(self):
        self.driver.get(LOGIN_URL)
        # Implementar login con Selenium
        # ...
    
    def get_assignments(self):
        # Implementar extracción con Selenium
        # ...
```

## 📝 Notas Importantes

- ⚠️ **Uso Responsable**: Este scraper es para uso personal únicamente
- 🔒 **Seguridad**: En el flujo legacy las credenciales están en `config.py`; en v2 se usan variables de entorno (`.env`, no versionado; ver `.env.example`). Entorno virtual: `ENV_README.md`.
- 📊 **Limitaciones**: Depende de la estructura HTML del portal
- 🔄 **Mantenimiento**: Puede requerir actualizaciones si el portal cambia

## 🆘 Soporte

Si encuentras problemas:

1. Revisa los archivos de debug en `debug_html/`
2. Verifica que las dependencias estén instaladas correctamente
3. Considera usar Selenium para portales con JavaScript
4. Revisa la estructura HTML del portal para actualizar los selectores

---

## LMS Agent Scraper (v2)

### Requisitos

- Python 3.10+
- Playwright: `pip install playwright && playwright install chromium`
- Variables de entorno en `.env` (copiar desde `.env.example`)

### Configuración

1. Copiar `.env.example` a `.env` y configurar:
   - `PORTAL_PROFILE` (ej: `moodle_unisimon` o `moodle_default`). **Para Unisimon Aula Pregrado (aulapregrado.unisimon.edu.co) usar `moodle_unisimon`.**
   - `PORTAL_BASE_URL`, `PORTAL_USERNAME`, `PORTAL_PASSWORD`
   - Opcional: `SCRAPER_DAYS_AHEAD`, `SCRAPER_DAYS_BEHIND`, `SCRAPER_MAX_COURSES`, `SCRAPER_OUTPUT_DIR`, `SCRAPER_DEBUG_MODE` (guardar HTML en `debug_html/` y más logs)
   - Opcional (Ollama): `OLLAMA_BASE_URL`, `OLLAMA_MODEL_NAME`, `OLLAMA_TEMPERATURE`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT` — usado para extraer la lista de cursos desde el HTML, clasificar páginas como “curso” en el discovery por contenido y (en el futuro) sugerir selectores. Requiere Ollama en ejecución y un modelo (p. ej. `ollama run glm-4.7-flash`). Ver [ollama.com/library/glm-4.7-flash](https://ollama.com/library/glm-4.7-flash). Si no está disponible, la extracción se hace con BeautifulSoup y Playwright.

2. Perfiles YAML en `profiles/` definen selectores, auth y opciones por portal (Moodle, Canvas, etc.). El perfil `moodle_unisimon` está ajustado para Unisimon Aula Pregrado e incluye `course_discovery` para el fallback por contenido.

### Detección de cursos (v2)

En la página "Mis cursos" del portal, la lista de cursos se obtiene en este orden:

1. **Enlaces por segmento de URL** — método principal: se buscan todos los enlaces cuya URL tenga en **algún segmento del path** una de las palabras clave configuradas (p. ej. `course`, `courses`, `cursos`). La comparación es **case-insensitive**. No depende de clases ni selectores CSS. Se configura con `course_link_segments` (lista) o `course_link_segment` (singular) en el perfil; si no se define, se usa por defecto `["course", "courses", "cursos"]`.
2. **BeautifulSoup (HTML)** — respaldo: se parsea el HTML con los selectores del perfil (tarjetas, nombre, enlace; ver esquema del bloque `courses` más abajo).
3. **LLM (Ollama)** — respaldo: si BeautifulSoup no devuelve cursos y Ollama está disponible, se envía un fragmento del HTML al modelo configurado para que devuelva un JSON con la lista de cursos (nombre y URL).
4. **Playwright** — respaldo: primero se prueban todos los enlaces de la página filtrados por las mismas palabras de segmento; si no hay resultados, se usan los locators del perfil (`courses.selectors`) dentro del contenedor opcional (`courses.container`).
5. **Discovery por contenido** — fallback opcional (perfil `course_discovery.fallback_when_empty: true`): si sigue habiendo 0 cursos, se extraen enlaces candidatos, se visitan y el LLM clasifica si son páginas de curso. Configurable con `max_candidates` y `candidate_patterns`.

Antes de extraer, se detecta la presencia de tarjetas de curso (`detect_courses_presence`) y, si el perfil lo indica, se puede expandir "Ver más" / paginación (`more_navigation`) antes de capturar el HTML.

#### Esquema del bloque `courses` en el perfil

Todos los campos son **opcionales**. Si no se definen, se usan valores por defecto compatibles con Moodle (block_myoverview / tarjetas). Así puedes reutilizar el mismo código en otros portales (Canvas, Blackboard, Moodle custom) solo configurando el perfil.

| Campo | Descripción | Por defecto (Moodle) |
|-------|-------------|----------------------|
| `course_link_segments` | Lista de palabras que identifican un enlace a curso si aparecen en algún segmento del path de la URL (case-insensitive). Ej.: `["course", "courses", "cursos"]`. | `["course", "courses", "cursos"]` |
| `course_link_segment` | Alternativa en singular (una sola palabra); se convierte en lista de un elemento. | — |
| `container` | Contenedor opcional para acotar la búsqueda (Playwright). | `[data-region='courses-view']` |
| `selectors` | Lista de selectores CSS para enlaces a curso (Playwright). | `a[href*='course/view.php']` |
| `card_selectors` | Selectores que identifican una tarjeta/ítem de curso (BeautifulSoup y detección de presencia). | `[data-region='course-content']`, `div.card.course-card` |
| `name_selectors` | Dentro de cada tarjeta, selectores para el nombre del curso (texto o `title`). | `a.coursename`, `span.multiline`, `[title]` |
| `link_selector` | Dentro de cada tarjeta, selector del enlace al curso. | Enlace cuyo `href` cumple `link_href_pattern` |
| `link_href_pattern` | Patrón que debe aparecer en el `href` (ej. `course/view`, `/course/`). | `course/view` |
| `fallback_containers` | Si no hay tarjetas, buscar enlaces dentro de estos contenedores. | `[data-region='courses-view']`, `.card-deck`, `.course-box` |
| `more_navigation` | Objeto opcional para "Ver más" / paginación antes de extraer. | No se expande |
| `more_navigation.selectors` | Lista de selectores (ej. `button:has-text('Ver más')`, `a:has-text('Siguiente')`). | — |
| `more_navigation.expand_before_extract` | Si `true`, hacer click en los controles antes de capturar HTML. | `false` |
| `more_navigation.max_clicks` | Número máximo de clicks en "Ver más" / siguiente. | `0` |

### Uso

```bash
# Instalar el paquete en modo editable (desde la raíz del repo)
pip install -e .

# Ejecutar scraper (perfil desde .env, ej. moodle_default)
python -m lms_agent_scraper.cli run

# Con perfil específico (recomendado para Unisimon Aula Pregrado)
python -m lms_agent_scraper.cli run --profile moodle_unisimon

# Modo debug: SCRAPER_DEBUG_MODE=true en .env para guardar HTML en debug_html/ y más logs

# Listar y validar perfiles
python -m lms_agent_scraper.cli profiles list
python -m lms_agent_scraper.cli profiles validate moodle_unisimon

# Tests (desde la raíz del repo)
pytest tests/ -v
```

### MCP Server (Cursor / Claude Desktop)

En la configuración MCP del cliente:

```json
{
  "mcpServers": {
    "lms-scraper": {
      "command": "python",
      "args": ["-m", "lms_agent_scraper.mcp.server"],
      "env": {
        "PORTAL_PROFILE": "moodle_unisimon",
        "PORTAL_BASE_URL": "${env:PORTAL_BASE_URL}",
        "PORTAL_USERNAME": "${env:PORTAL_USERNAME}",
        "PORTAL_PASSWORD": "${env:PORTAL_PASSWORD}"
      }
    }
  }
}
```

Herramientas expuestas: `get_pending_assignments`, `get_submitted_assignments`, `get_courses`, `generate_report`, `check_deadlines`, `list_profiles`. El servidor envía `instructions` al cliente indicando que se trata del portal LMS de la **Universidad Simón Bolívar (Unisimon), Aula Pregrado**, para que el agente tenga ese contexto.

### Desarrollo con Cursor

Este proyecto se desarrolla con Cursor. Se usan **reglas globales** en `~/.cursor/rules/` (aplican a todos los proyectos):

- **SOLID y calidad**: `solid-and-quality.mdc` — principios SOLID, DRY y buenas prácticas. Copia en el repo: [docs/SOLID_AND_QUALITY.md](docs/SOLID_AND_QUALITY.md). Verificación de cumplimiento: [docs/ARCHITECTURE_VERIFICATION.md](docs/ARCHITECTURE_VERIFICATION.md).
- **Idioma**: `comments-spanish-code-english.mdc` — comentarios y docstrings en español; nombres de código en inglés.

**MCPs opcionales** (instalados en `C:\MCPs\` y configurados en `~/.cursor/mcp.json`):

| MCP | Descripción |
|-----|-------------|
| **pdf-reader** | Lee texto de archivos PDF. |
| **char-counter** | Cuenta caracteres, palabras y líneas en texto o archivo. |
| **unused-vars** | Analiza código Python y detecta variables/funciones no usadas y variables de entorno referenciadas; opcionalmente compara con un `.env`. |

Para analizar este repo con unused-vars (y opcionalmente el `.env`), el agente puede llamar a la herramienta `analyze_unused` con `path` al directorio del proyecto y `env_file` al `.env`.

### Agent Skills (skills.sh)

Para mejorar el comportamiento de agentes al trabajar con este repo, instala skills desde [skills.sh](https://skills.sh/). Se instalan en **`.agents/skills/`** y **Cursor (y otros agentes compatibles) los usan automáticamente** al trabajar en este repositorio. En `docs/AGENT_SKILLS.md` encontrarás la lista por prioridad, la tabla labores–skills y la integración con los agentes.

**Esenciales:** `vercel-labs/agent-browser`, `anthropics/skills` (incluye pdf y webapp-testing). **Recomendados:** `browser-use/browser-use`, `obra/superpowers`. **Opcionales:** `wshobson/agents`.

```bash
npx skills add vercel-labs/agent-browser --yes
npx skills add anthropics/skills --yes
npx skills add browser-use/browser-use --yes
npx skills add obra/superpowers --yes
```

Ver `docs/AGENT_SKILLS.md` para todos los comandos y `npx skills list` para listar los instalados.

**Skills en tiempo de ejecución (prompts del LLM):** Los prompts que usa Ollama están en `src/lms_agent_scraper/skills/` (archivos SKILL.md por tarea: extracción de cursos, fechas, selectores, etc.). Puedes editarlos sin tocar código. Para validar que carguen bien: `python validate_skills.py`. Detalle en `docs/AGENT_SKILLS.md` (sección "Skills en tiempo de ejecución").

---

## 📄 Licencia

Este proyecto es para uso educativo y personal únicamente.
