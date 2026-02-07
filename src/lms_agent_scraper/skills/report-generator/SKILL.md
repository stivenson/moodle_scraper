---
name: report-generator
description: Define el formato del reporte Markdown de tareas mediante un recurso plantilla (report_template.md)
version: 1.0.0
category: report
author: LMS Agent Scraper
tags:
  - report
  - template
  - markdown
---

# Report Generator Skill

Este skill no contiene prompts para el LLM; aporta el recurso **report_template.md** con la plantilla del reporte de tareas. El generador de reportes rellena la plantilla con el contexto (título, fecha, tareas por sección, etc.).

## Report Template

El archivo **report_template.md** en esta carpeta usa placeholders en formato `{nombre}` rellenados con `str.format()`. Variables disponibles:

- **title**: Título del reporte (ej. desde perfil `reports.title_template`).
- **generation_date**: Fecha/hora de generación.
- **period**: Texto del período consultado (últimos N días y próximos N días).
- **total_tasks**: Número total de tareas.
- **courses_count_line**: Línea opcional "**Cursos encontrados:** N" o cadena vacía.
- **courses_explored_section**: Sección "## Cursos explorados" con lista en Markdown de nombres de cursos (puede ser vacía).
- **section_recently_submitted**: Bloque Markdown de tareas entregadas recientemente (puede ser vacío).
- **section_overdue**: Bloque de tareas atrasadas.
- **section_due_today**: Bloque de tareas que vencen hoy.
- **section_upcoming**: Bloque de próximas tareas.
- **empty_message**: Mensaje cuando no hay tareas en el período (ej. "## Sin tareas pendientes...").
- **footer**: Pie del reporte (ej. "*Reporte generado por LMS Agent Scraper*").
