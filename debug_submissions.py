#!/usr/bin/env python3
"""
Script opcional de depuración para revisar la detección del estado de entrega
(submission status) con el scraper legacy híbrido (Selenium + spaCy).

Uso: python debug_submissions.py

Requisitos:
- .env configurado (o variables de entorno): PORTAL_BASE_URL, PORTAL_LOGIN_PATH, PORTAL_USERNAME, PORTAL_PASSWORD (config.py los lee desde .env).
- Google Chrome instalado (Selenium usa Chrome/ChromeDriver; si no tienes Chrome,
  usa el flujo v2: python -m lms_agent_scraper.cli run con Playwright).
- pip install -r requirements.txt (selenium, webdriver-manager, spacy, etc.).

No es parte del flujo v2 (python -m lms_agent_scraper.cli run).
"""

from scraper_hybrid import UnisimonScraperHybrid
from config import *

def debug_submissions():
    scraper = UnisimonScraperHybrid()
    scraper.setup_driver()
    
    if not scraper.login_with_selenium():
        print("Login failed")
        return
    
    course_links = scraper.get_course_links_with_selenium()
    if not course_links:
        print("No courses found")
        return
    
    all_assignments = []
    for course in course_links[:1]:  # Solo el primer curso para debug
        print(f"Processing course: {course['name']}")
        assignments = scraper.extract_assignments_with_spacy(course['name'], course['url'])
        all_assignments.extend(assignments)
    
    print(f"\nTotal assignments found: {len(all_assignments)}")
    
    # Buscar tareas con estado 'Enviado para calificar'
    submitted = [a for a in all_assignments if a.get('submission_status', {}).get('submitted', False)]
    print(f"\nTareas con submitted=True: {len(submitted)}")
    for i, a in enumerate(submitted[:5]):
        print(f"{i+1}. {a.get('title', 'Sin título')}")
        print(f"   Status: {a.get('submission_status', {})}")
        print()
    
    # Buscar tareas con 'Enviado para calificar' en el texto
    enviado = [a for a in all_assignments if 'enviado' in str(a.get('submission_status', {})).lower()]
    print(f"\nTareas con 'enviado' en status: {len(enviado)}")
    for i, a in enumerate(enviado[:5]):
        print(f"{i+1}. {a.get('title', 'Sin título')}")
        print(f"   Status: {a.get('submission_status', {})}")
        print()
    
    # Buscar tareas con 'Enviado para calificar' en el status_text
    enviado_text = [a for a in all_assignments if 'enviado' in a.get('submission_status', {}).get('status_text', '').lower()]
    print(f"\nTareas con 'enviado' en status_text: {len(enviado_text)}")
    for i, a in enumerate(enviado_text[:5]):
        print(f"{i+1}. {a.get('title', 'Sin título')}")
        print(f"   Status: {a.get('submission_status', {})}")
        print()
    
    scraper.driver.quit()

if __name__ == "__main__":
    debug_submissions()
