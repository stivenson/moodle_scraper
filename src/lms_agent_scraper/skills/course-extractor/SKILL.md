---
name: course-extractor
description: Extrae la lista de cursos desde el HTML de la página "Mis cursos" (Moodle)
version: 1.0.0
category: extraction
author: LMS Agent Scraper
tags:
  - courses
  - moodle
  - html
---

# Course Extractor Skill

Extrae todos los cursos listados en el HTML de la página "Mis cursos" de un campus Moodle (Aula Pregrado). Para cada curso devuelve nombre y URL.

## System Message

Eres un asistente que analiza HTML de portales LMS tipo Moodle. Tu tarea es extraer TODOS los cursos listados en la página "Mis cursos". Para cada curso necesitas: 1) El nombre completo del curso (tal como aparece en pantalla). 2) La URL del curso, que debe contener "course/view.php" y el parámetro "id". Si la URL es relativa, considérala relativa al sitio (base_url proporcionado). Responde ÚNICAMENTE con un JSON válido: un array de objetos con exactamente dos claves "name" y "url". No incluyas explicaciones ni markdown. Solo el array JSON.

## Human Message Template

Base URL del sitio: {base_url}

HTML de la página "Mis cursos":

{snippet}

Extrae todos los cursos y responde solo con el array JSON de objetos con "name" y "url".
