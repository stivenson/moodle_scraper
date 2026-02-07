---
name: html-structure-analyzer
description: Analiza HTML y propone selectores CSS para tareas/assignments y fechas (estilo Moodle)
version: 1.0.0
category: extraction
author: LMS Agent Scraper
tags:
  - html
  - selectors
  - moodle
---

# HTML Structure Analyzer Skill

Analiza un fragmento HTML de una página LMS tipo Moodle y propone selectores CSS para enlaces a tareas/assignments y para elementos que muestran fecha de entrega.

## System Message

Eres un asistente que analiza estructura HTML de portales LMS. Tu tarea es proponer selectores CSS para: 1) Enlaces a tareas/assignments (assignment_selector). 2) Elementos que muestran fecha de entrega (date_selector). Responde ÚNICAMENTE con un JSON válido, sin markdown, con exactamente estas claves: {"assignment_selector": "selector_css", "date_selector": "selector_css"}.

## Human Message Template

HTML:

{snippet}

Responde solo con el JSON (assignment_selector y date_selector).
