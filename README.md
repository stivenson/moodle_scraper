# Unisimon Portal Scraper / LMS Agent Scraper

Un scraper automatizado para extraer tareas pendientes del portal de Unisimon Aula Pregrado.

**Versión 2 (LMS Agent Scraper):** Framework generalizado con LangGraph, perfiles YAML, MCP y soporte para múltiples portales LMS. Ver sección "Uso LMS Agent Scraper (v2)" más abajo.

## 🚀 Características

- ✅ Autenticación automática en el portal
- 📅 Filtrado de tareas por período personalizable (configurable en días)
- 📊 Generación de reportes en formato Markdown
- 🔍 Modo debug para análisis del portal
- 🛠️ Preparado para migración a Selenium si es necesario

## 📁 Estructura del Proyecto

```
unisimon_scraper/
├── scraper.py          # Script principal
├── config.py           # Configuración y credenciales
├── utils.py            # Funciones auxiliares
├── requirements.txt    # Dependencias
└── README.md          # Este archivo
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
- 🔒 **Seguridad**: Las credenciales se almacenan en texto plano en `config.py`
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
   - `PORTAL_PROFILE` (ej: `moodle_default` o `moodle_unisimon`)
   - `PORTAL_BASE_URL`, `PORTAL_USERNAME`, `PORTAL_PASSWORD`
   - Opcional: `SCRAPER_DAYS_AHEAD`, `SCRAPER_DAYS_BEHIND`
   - Opcional (Ollama): `OLLAMA_BASE_URL`, `OLLAMA_MODEL_NAME`, `OLLAMA_TEMPERATURE`, `OLLAMA_NUM_CTX`, `OLLAMA_NUM_PREDICT`, `OLLAMA_REQUEST_TIMEOUT` — método principal para extraer la lista de cursos cuando Ollama está disponible; también para el agente analizador de selectores. Si Ollama no está disponible, se usan Playwright y BeautifulSoup como respaldo. Requiere Ollama en ejecución y un modelo (p. ej. `ollama run glm-4.7-flash`). Ver [ollama.com/library/glm-4.7-flash](https://ollama.com/library/glm-4.7-flash).

2. Perfiles YAML en `profiles/` definen selectores por tipo de portal (Moodle, Canvas, etc.).

### Detección de cursos (v2)

En la página "Mis cursos" del portal, la lista de cursos se obtiene así:

1. **LLM (Ollama)** — método principal: si Ollama está disponible, se envía un fragmento del HTML al modelo configurado (p. ej. GLM-4.7-Flash) para que devuelva un JSON con la lista de cursos (nombre y URL). Requiere Ollama en ejecución y el modelo descargado.
2. **Playwright** — respaldo: si el LLM no está disponible o no devuelve cursos, se espera a las tarjetas (p. ej. `[data-region='course-content']` o `.course-card`) y se extraen enlaces con los locators del perfil.
3. **BeautifulSoup** — respaldo: si aún no hay cursos, se parsea el HTML y se buscan tarjetas, enlaces con clase `coursename` y URLs a `course/view.php`.

### Uso

```bash
# Instalar el paquete en modo editable (desde la raíz del repo)
pip install -e .

# Ejecutar scraper
python -m lms_agent_scraper.cli run

# Con perfil específico
python -m lms_agent_scraper.cli run --profile moodle_default

# Listar y validar perfiles
python -m lms_agent_scraper.cli profiles list
python -m lms_agent_scraper.cli profiles validate moodle_default
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
        "PORTAL_PROFILE": "moodle_default",
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

- **SOLID y calidad**: `solid-and-quality.mdc` — principios SOLID, DRY y buenas prácticas.
- **Idioma**: `comments-spanish-code-english.mdc` — comentarios y docstrings en español; nombres de código en inglés.

**MCPs opcionales** (instalados en `C:\MCPs\` y configurados en `~/.cursor/mcp.json`):

| MCP | Descripción |
|-----|-------------|
| **pdf-reader** | Lee texto de archivos PDF. |
| **char-counter** | Cuenta caracteres, palabras y líneas en texto o archivo. |
| **unused-vars** | Analiza código Python y detecta variables/funciones no usadas y variables de entorno referenciadas; opcionalmente compara con un `.env`. |

Para analizar este repo con unused-vars (y opcionalmente el `.env`), el agente puede llamar a la herramienta `analyze_unused` con `path` al directorio del proyecto y `env_file` al `.env`.

### Agent Skills (skills.sh)

Para mejorar el comportamiento de agentes al trabajar con este repo, instala skills recomendados:

```bash
npx skills add vercel-labs/agent-browser
npx skills add anthropics/pdf
```

Ver `docs/AGENT_SKILLS.md` para la lista completa.

---

## 📄 Licencia

Este proyecto es para uso educativo y personal únicamente.
