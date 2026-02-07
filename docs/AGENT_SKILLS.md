# Agent Skills (skills.sh)

Para mejorar el comportamiento de agentes (Cursor, Claude, etc.) al trabajar con este proyecto, puedes instalar skills desde [skills.sh](https://skills.sh/). Los skills son capacidades reutilizables para agentes de IA; se instalan con `npx skills add <owner/repo>` y son compatibles con Cursor y otros agentes del ecosistema.

## Skills por prioridad

### Esenciales (scraper, reportes y pruebas web)

- **`vercel-labs/agent-browser`** — Automatización de navegador; mejora la depuración y los flujos con Playwright.
- **`anthropics/pdf`** — Generación de reportes en PDF (el proyecto genera Markdown hoy; este skill permite añadir salida PDF).
- **`anthropics/webapp-testing`** — Testing de interacciones web; alinea con validación de login, cursos y entregas en el portal.

### Recomendados (browser avanzado y debugging/tests)

- **`browser-use/browser-use`** — Browser automation avanzada; complemento a agent-browser.
- **`obra/superpowers`** — Incluye systematic-debugging, test-driven-development, writing-plans, executing-plans; útil para depurar el scraper y extender tests.

### Opcionales (Python testing, E2E, MCP)

- **`wshobson/agents`** — python-testing-patterns, e2e-testing-patterns, debugging-strategies (stack Python y E2E).
- **`anthropics/skills`** — mcp-builder; útil si vas a ampliar o mantener el servidor MCP del proyecto.

## Skills por labor del proyecto

| Labor del proyecto | Skill(s) en skills.sh | Justificación |
|-------------------|------------------------|---------------|
| Automatización de navegador (login, discovery, scraping) | `vercel-labs/agent-browser`, `browser-use/browser-use` | Mejoran depuración y flujos con Playwright; el agente entiende mejor patrones de browser automation. |
| Generación de reportes (Markdown hoy; PDF deseable) | `anthropics/pdf` | Permite que el agente genere o mejore reportes en PDF además de Markdown. |
| Probar flujos en el portal (login, cursos, entregas) | `anthropics/webapp-testing` | Alinea con tests E2E y validación del flujo en el portal. |
| Depuración del scraper y fallos de selectores | `obra/superpowers` (systematic-debugging) | Guía para depurar de forma ordenada cuando fallan login o selectores. |
| Tests (pytest, workflow, MCP) | `obra/superpowers` (test-driven-development), `wshobson/agents` (python-testing-patterns) | Patrones de tests en Python y TDD al extender tests. |
| Mantenimiento/evolución del servidor MCP | `anthropics/skills` (mcp-builder) | Útil si el agente va a añadir o cambiar herramientas MCP. |

## Instalación

Desde la raíz del proyecto (o desde cualquier directorio donde quieras que se registren los skills):

### Esenciales (scraper + reportes + pruebas web)

```bash
npx skills add vercel-labs/agent-browser --yes
npx skills add anthropics/skills --yes
```

El repo `anthropics/skills` incluye los skills **pdf** y **webapp-testing** (entre otros). Si prefieres instalar solo uno, prueba `npx skills add anthropics/pdf` o `npx skills add anthropics/webapp-testing` (pueden requerir acceso al repo).

### Recomendados (browser avanzado + debugging/tests)

```bash
npx skills add browser-use/browser-use --yes
npx skills add obra/superpowers --yes
```

### Opcionales (Python testing, E2E)

```bash
npx skills add wshobson/agents --yes
```

### Instalar todos los recomendados (esenciales + recomendados)

```bash
npx skills add vercel-labs/agent-browser --yes
npx skills add anthropics/skills --yes
npx skills add browser-use/browser-use --yes
npx skills add obra/superpowers --yes
```

## Uso a nivel de proyecto e integración con agentes

Los skills se instalan **en el proyecto** en la carpeta **`.agents/skills/`**. Cada skill es un directorio con un `SKILL.md` y recursos que definen conocimiento y procedimientos para el agente.

- **Integración con Cursor (y otros agentes):** Cursor y los agentes compatibles con [skills.sh](https://skills.sh/) leen automáticamente la carpeta `.agents/skills/` cuando trabajas en este repositorio. No hace falta configuración adicional: al abrir el proyecto, el agente tiene acceso a los skills instalados (agent-browser, pdf, webapp-testing, browser-use, systematic-debugging, test-driven-development, mcp-builder, etc.) y los usa cuando la tarea lo requiere.
- **Listar lo instalado:** desde la raíz del proyecto ejecuta `npx skills list` para ver todos los skills de proyecto.
- **Versionado:** la carpeta `.agents/` no está en `.gitignore`, por lo que los skills quedan versionados y todo el equipo obtiene el mismo conjunto al clonar. Si prefieres que cada desarrollador instale los skills con los comandos de esta página, puedes añadir `.agents/` al `.gitignore`.

## Listar skills instalados

```bash
npx skills list
```

Estos skills mejoran la capacidad del agente para depurar el scraper, generar reportes en PDF, probar flujos en el portal y mantener tests y el servidor MCP.

---

## Skills en tiempo de ejecución (prompts en SKILL.md)

Además de los skills de [skills.sh](https://skills.sh/) (para la IDE), este proyecto usa **skills en tiempo de ejecución**: los prompts que recibe el LLM (Ollama) están externalizados en archivos **SKILL.md** dentro del paquete. Así se pueden editar y versionar sin tocar código.

### Diferencia con skills.sh

- **skills.sh** (carpeta `.agents/skills/`): los usa **Cursor** (u otro agente de la IDE) cuando trabajas en el repo; no los ejecuta el código del scraper.
- **Skills en tiempo de ejecución** (`src/lms_agent_scraper/skills/`): los lee el **SkillLoader** y los usa **LocalLLMClient** al llamar a Ollama (extracción de cursos, clasificación de página, fechas, selectores). Son los prompts que recibe el modelo cuando corres el workflow.

### Dónde están

Cada skill es una carpeta bajo **`src/lms_agent_scraper/skills/`** con un archivo **`SKILL.md`** que tiene:

- **Frontmatter YAML:** `name`, `description`, `version`, etc.
- **Secciones:** `## System Message` y `## Human Message Template` (con variables como `{snippet}`, `{date_text}`, `{context}`) para los skills de prompts. Algunos skills solo aportan **recursos** (archivos adicionales en la carpeta).

Skills disponibles: `date-interpreter`, `course-extractor`, `course-page-classifier`, `selector-suggester`, `html-structure-analyzer`, `report-generator`.

El skill **report-generator** no define prompts para el LLM; incluye el recurso **report_template.md**, que es la plantilla Markdown del reporte de tareas. El generador de reportes ([report_tools](src/lms_agent_scraper/tools/report_tools.py)) carga esa plantilla con `SkillLoader.load_skill_resource()` y la rellena con el contexto (título, fecha, tareas por sección, etc.). Si el recurso no existe, la generación del reporte falla con un error explícito.

### Cómo funciona

El **SkillLoader** ([core/skill_loader.py](src/lms_agent_scraper/core/skill_loader.py)) lee el SKILL.md, parsea YAML y secciones, y construye un `ChatPromptTemplate` (LangChain). **LocalLLMClient** intenta cargar el skill correspondiente a cada tarea (p. ej. `date-interpreter` para interpretar fechas); si el skill existe y carga bien, usa ese prompt; si no, usa el prompt hardcodeado (retrocompatibilidad).

### Cómo añadir o editar un skill

1. Crea o edita la carpeta `src/lms_agent_scraper/skills/<nombre-skill>/SKILL.md`.
2. Usa el formato: frontmatter `---` YAML `---` y secciones `## System Message` y `## Human Message Template` con las variables que necesites (p. ej. `{snippet}`, `{date_text}`).
3. Valida con: `python validate_skills.py` desde la raíz del repo.

### Validar skills

Desde la raíz del proyecto (con el paquete instalable en el path, p. ej. `pip install -e .` o `PYTHONPATH=src`):

```bash
python validate_skills.py
```

Comprueba que cada skill exista, tenga el formato correcto y las variables esperadas en el Human Message Template.
