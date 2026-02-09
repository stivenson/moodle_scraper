# Verificación: arquitectura de agentes, variables no usadas y SOLID

## 1. Arquitectura actual de agentes (sin redundancia de lógica)

### Flujo del grafo (workflow)

```
Start → authenticate → course_discovery → assignment_extractor → data_processor → report_generator → End
```

- **authenticate**: [`nodes.authentication_node`] → llama a **browser_tools.login_with_playwright** (o a `config["configurable"]["login_fn"]` si se inyecta).
- **course_discovery**: [`nodes.course_discovery_node`] → llama a **browser_tools.get_course_links_with_playwright** (o a `config["configurable"]["get_courses_fn"]` si se inyecta), que internamente delega en `_try_extract_courses_step_by_step`:
  1. Opcional: expande "Ver más" / paginación si el perfil define `courses.more_navigation`.
  2. Detecta presencia de tarjetas (`detect_courses_presence`) y captura HTML.
  3. Paso 0: extracción por segmento de URL (`_extract_courses_by_link_segment`).
  4. Paso 1: **BeautifulSoup** (`_extract_courses_bs4`).
  5. Paso 2: **LLM (Ollama)** (`_extract_courses_llm`; opcional `llm_client` inyectable).
  6. Paso 3: **selectores Playwright**.
  7. Fallback (si `course_discovery.fallback_when_empty`): **agents.course_discovery_agent.discover_courses_by_visiting_links**.
- **assignment_extractor**: usa **extraction_tools.get_assignments_for_courses**.
- **report_generator**: usa **report_tools.generate_markdown_report** y **save_report**.

No hay duplicación de lógica: login está solo en `login_with_playwright`; descubrimiento de cursos está orquestado en `get_course_links_with_playwright` y el agente por contenido es un fallback más.

### Módulos en `agents/`

| Módulo | Usado por el workflow | Notas |
|--------|------------------------|--------|
| **course_discovery_agent** | Sí | Llamado desde `browser_tools.get_course_links_with_playwright` cuando hay 0 cursos y `fallback_when_empty: true`. |
| **login_agent** | No | Expone `run_auth` y `create_auth_runner`; el grafo usa directamente `nodes.authentication_node` → `login_with_playwright`. API alternativa, no redundante (misma implementación en browser_tools). |
| **analyzer_agent** | No | `run_error_analysis` e `interpret_dates_with_llm` no están referenciados en el repo. Código preparado para uso futuro (reintentos con selectores sugeridos, fechas con LLM). |

Conclusión: no hay redundancia de lógica. La única “doble vía” es auth: nodo del grafo vs. API en `login_agent`, ambos delegando en `login_with_playwright`.

---

## 2. Variables / símbolos no usados (MCP unused-vars)

Resultado del MCP **unused-vars** sobre `src/lms_agent_scraper` (resumen interpretado):

### Falsos positivos (sí se usan)

- **Nodos del grafo** (`authentication_node`, `course_discovery_node`, etc.): se usan vía `nodes.*` en `workflow.py` y en tests.
- **Funciones de tools** (`get_course_links_with_playwright`, `login_with_playwright`, etc.): usadas desde `nodes` o desde MCP/server.
- **CLI** (`run`, `profiles_list`, `profiles_validate`, `mcp_serve`): comandos registrados con Typer; el MCP no detecta ese uso.
- **Config/state** (ej. `ScraperState`, `PortalSettings`): usados por workflow, CLI o MCP.
- **course_discovery_agent.discover_courses_by_visiting_links**: usada desde `browser_tools` (import dentro de un `if`); el analizador estático puede no seguir ese uso.

### Corregido

- **graph/nodes.py**: se eliminó el import no usado `Path` (no se usaba en el archivo).

### Código no referenciado (opcional limpiar o conectar)

- **agents/analyzer_agent**: `run_error_analysis`, `interpret_dates_with_llm` — no referenciados. Opciones: (1) Conectar en el grafo (ej. nodo de reintento que use `run_error_analysis`), (2) Dejar como API futura y documentar, (3) Eliminar si no se planea usar.
- **agents/login_agent**: `create_auth_runner` y `run_auth` — no usados por el workflow. Útiles como API programática; no redundantes con la lógica (la lógica está en browser_tools).

---

## 3. Regla SOLID y calidad (¿se están teniendo en cuenta?)

**Regla de referencia:** `~/.cursor/rules/solid-and-quality.mdc` (reglas generales de Cursor, `alwaysApply: true`). Copia en el repo: [docs/SOLID_AND_QUALITY.md](SOLID_AND_QUALITY.md). Exige: **S** una única razón para cambiar; **O** extensión sin modificación; **L** sustitución de subtipos; **I** interfaces pequeñas; **D** depender de abstracciones e inyectar dependencias; **DRY**; nombres descriptivos y funciones acotadas.

**¿Se están teniendo en cuenta?** La regla existe y aplica a todo el código. El código actual **no cumple del todo** en varios puntos (abajo). A partir de esta verificación deben aplicarse en todo nuevo código y refactor.

### Incumplimientos concretos (mitigados en refactors recientes)

| Principio | Dónde | Qué ocurre / mejora aplicada |
|----------|--------|------------------------------|
| **S** | `browser_tools.py` | Sigue agrupando login y discovery; se extrajeron `_extract_courses_bs4`, `_extract_courses_llm` y `_try_extract_courses_step_by_step` para acotar pasos. |
| **S** | `ollama_client.py` | Se extrajeron por dominio `_run_course_extractor`, `_run_page_classifier` y helper `_strip_markdown_and_parse_json`; la interfaz pública se mantiene. |
| **D** | `graph/nodes.py` | **Mitigado**: los nodos aceptan `config` opcional; `config["configurable"]["login_fn"]` y `get_courses_fn` permiten inyectar mocks en tests. |
| **D** | `browser_tools` | **Mitigado**: `get_course_links_with_playwright` y `_extract_courses_llm` aceptan `llm_client` opcional; por defecto se usa LocalLLMClient(). |
| **Funciones acotadas** | `get_course_links_with_playwright` | **Mitigado**: la lógica de extracción está en `_try_extract_courses_step_by_step`; la función pública orquesta y delega. |

### Cumplimientos

- **O**: Extensión por perfiles YAML y `course_discovery`. **L**: Poca herencia. **I**: Sin interfaces gordas. **Nodos**: responsabilidad clara cada uno. **course_discovery_agent**: responsabilidad acotada.

Revisión detallada anterior (manual):

- **S (Single responsibility)**  
  - **browser_tools**: agrupa login, listado de cursos (BS4 + LLM + selectores Playwright) y orquestación del fallback por contenido. Podría dividirse en “login” vs “course discovery” si se busca SRP estricto.  
  - **ollama_client**: varias responsabilidades (análisis HTML, fechas, selectores, extracción de cursos, clasificación de página). Cohesión por “uso del LLM”; aceptable; si crece, separar por dominio (ej. “course classifier”, “date interpreter”).  
  - **Nodos**: cada uno tiene una responsabilidad clara (auth, cursos, tareas, proceso, reporte).  
  - **course_discovery_agent**: una responsabilidad (descubrir cursos visitando enlaces y clasificando con LLM). Bien.

- **O (Open/Closed)**  
  - Comportamiento extendido por perfiles YAML (nuevos LMS/portales sin tocar código).  
  - Estrategias de descubrimiento configurables (`course_discovery.fallback_when_empty`, `candidate_patterns`). Bien.

- **L (Liskov)**  
  - Poca herencia; estado con TypedDict. Nada que rompa sustituciones.

- **I (Interface segregation)**  
  - No hay interfaces formales; se usan dicts y funciones. Los contratos están en firmas y docstrings. Aceptable para el tamaño actual.

- **D (Dependency inversion)**  
  - Nodos dependen de funciones concretas (browser_tools, extraction_tools, report_tools). Para tests se podría inyectar dependencias (ej. `login_fn`, `get_courses_fn`); por ahora no hay abstracciones.

Resumen: la estructura es coherente con SOLID para el tamaño del proyecto; los puntos mejorables son concentración de responsabilidades en `browser_tools`/`ollama_client` y falta de inyección de dependencias para tests.

---

## 4. Optimizaciones aplicadas (plan de mejoras seguras)

Tras aplicar el plan de optimizaciones seguras se realizó:

- **browser_tools**: Renombrado `_extract_courses_from_html` → `_extract_courses_bs4`, `_extract_courses_with_llm` → `_extract_courses_llm`; extraída `_try_extract_courses_step_by_step` para agrupar los pasos de extracción. Parámetro opcional `llm_client` en `get_course_links_with_playwright` y `_extract_courses_llm`.
- **ollama_client**: Métodos por dominio `_run_course_extractor` y `_run_page_classifier`; helper `_strip_markdown_and_parse_json` para evitar duplicación de parseo JSON. La API pública no cambia.
- **graph/nodes**: Nodos `authentication_node` y `course_discovery_node` aceptan segundo argumento `config` opcional; desde `config["configurable"]` se pueden inyectar `login_fn` y `get_courses_fn` para tests.
- **agents (analyzer_agent, login_agent)**: Documentados como API futura en docstrings.
- **Tests**: Añadidos tests para ollama_client, skill_loader, nodos (data_processor, report_generator) y test de inyección de `login_fn` en authentication_node.
- **Ruff**: Ejecutado check y format; corregidos imports y orden de módulos.

---

## 5. Resumen

| Aspecto | Estado |
|---------|--------|
| Redundancia de lógica | No hay; un solo lugar por responsabilidad (login en browser_tools; discovery orquestado en get_course_links_with_playwright con el agente como fallback). |
| Variables/símbolos no usados | Corregido import `Path` en nodes. analyzer_agent y login_agent tienen funciones no usadas por el workflow; opcional documentar o conectar. |
| SOLID | Regla en `~/.cursor/rules/solid-and-quality.mdc` (alwaysApply). Incumplimientos mitigados en refactors (§3); ver §4. Se deben tener en cuenta en todo nuevo código y refactor. |
