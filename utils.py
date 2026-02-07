# Utility functions for Unisimon Portal Scraper
# =============================================

import os
from datetime import datetime, timedelta
from typing import List, Dict, Any
import re

def filter_by_date(assignments: List[Dict[str, Any]], days_ahead: int, days_behind: int = 0) -> List[Dict[str, Any]]:
    """
    Filter assignments that are due within the specified time range.
    
    Args:
        assignments: List of assignment dictionaries
        days_ahead: Number of days to look ahead
        days_behind: Number of days to look behind (for overdue assignments)
        
    Returns:
        Filtered list of assignments due within the time window
    """
    if not assignments:
        return []
    
    today = datetime.now().date()
    future_cutoff = today + timedelta(days=days_ahead)
    past_cutoff = today - timedelta(days=days_behind)
    
    filtered_assignments = []
    
    for assignment in assignments:
        due_date = parse_date(assignment.get('due_date', ''))
        if due_date:
            # Include assignments that are:
            # 1. Due in the future (up to days_ahead)
            # 2. Overdue (up to days_behind in the past)
            if (due_date <= future_cutoff and due_date >= today) or \
               (due_date < today and due_date >= past_cutoff):
                # Add status information
                assignment_copy = assignment.copy()
                if due_date < today:
                    assignment_copy['status'] = 'OVERDUE'
                    days_overdue = (today - due_date).days
                    assignment_copy['days_overdue'] = days_overdue
                elif due_date == today:
                    assignment_copy['status'] = 'DUE_TODAY'
                    assignment_copy['days_until_due'] = 0
                else:
                    days_until_due = (due_date - today).days
                    assignment_copy['status'] = 'UPCOMING'
                    assignment_copy['days_until_due'] = days_until_due
                
                filtered_assignments.append(assignment_copy)
    
    return filtered_assignments

def parse_date(date_string: str) -> datetime.date:
    """
    Parse various date formats from the portal.
    
    Args:
        date_string: Date string from the portal
        
    Returns:
        Parsed date object or None if parsing fails
    """
    if not date_string:
        return None
    
    # Clean the date string
    date_string = date_string.strip()
    
    # Skip obviously invalid dates
    if "31-12-1969" in date_string or "1969" in date_string:
        return None
    
    # Common date formats to try
    date_formats = [
        '%Y-%m-%d',           # 2024-01-15
        '%d/%m/%Y',           # 15/01/2024
        '%d-%m-%Y',           # 15-01-2024
        '%d/%m/%y',           # 15/01/24
        '%d-%m-%y',           # 15-01-24
        '%B %d, %Y',          # January 15, 2024
        '%d %B %Y',           # 15 January 2024
        '%d de %B de %Y',     # 23 de octubre de 2025
        '%Y-%m-%d %H:%M:%S',  # 2024-01-15 14:30:00
        '%d/%m/%Y %H:%M',     # 15/01/2024 14:30
    ]
    
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_string, fmt).date()
            # Check if date is reasonable (not too far in past or future)
            current_year = datetime.now().year
            if 2020 <= parsed_date.year <= current_year + 2:
                return parsed_date
        except ValueError:
            continue
    
    # Try to extract date using regex patterns
    date_patterns = [
        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # DD/MM/YYYY
        r'(\d{1,2})-(\d{1,2})-(\d{4})',  # DD-MM-YYYY
        r'(\d{1,2})/(\d{1,2})/(\d{2})',  # DD/MM/YY
        r'(\d{1,2})-(\d{1,2})-(\d{2})',  # DD-MM-YY
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, date_string)
        if match:
            try:
                if pattern.startswith(r'(\d{4})'):  # YYYY-MM-DD
                    year, month, day = match.groups()
                    year = int(year)
                else:  # DD/MM/YYYY or DD-MM-YYYY or DD/MM/YY or DD-MM-YY
                    day, month, year = match.groups()
                    year = int(year)
                    # Handle 2-digit years
                    if year < 100:
                        year += 2000 if year < 50 else 1900
                
                parsed_date = datetime(int(year), int(month), int(day)).date()
                # Check if date is reasonable
                current_year = datetime.now().year
                if 2020 <= parsed_date.year <= current_year + 2:
                    return parsed_date
            except ValueError:
                continue
    
    return None

def generate_markdown_report(assignments: List[Dict[str, Any]], days_ahead: int, days_behind: int = 0, all_assignments: List[Dict[str, Any]] = None, courses_count: int = None) -> str:
    """
    Generate a markdown report from the extracted assignments.
    
    Args:
        assignments: List of assignment dictionaries (filtered)
        days_ahead: Number of days ahead that were checked
        days_behind: Number of days behind that were checked
        all_assignments: All assignments (for recently submitted)
        courses_count: Optional number of courses found (shown in report if provided)
        
    Returns:
        Markdown formatted report string
    """
    if not assignments and not all_assignments:
        return generate_empty_report(days_ahead, days_behind, courses_count=courses_count)
    
    # Use all_assignments if provided, otherwise use assignments
    all_assignments = all_assignments or assignments
    
    # Group assignments by course
    courses = {}
    for assignment in all_assignments:
        course_name = assignment.get('course', 'Sin curso')
        if course_name not in courses:
            courses[course_name] = []
        courses[course_name].append(assignment)
    
    # Generate report content
    report_lines = []
    
    # Header
    report_lines.append("# 📚 Reporte de Tareas - Unisimon")
    report_lines.append("")
    report_lines.append(f"**Fecha de generación:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    report_lines.append(f"**Período consultado:** Últimos {days_behind} días y Próximos {days_ahead} días")
    report_lines.append(f"**Total de tareas encontradas:** {len(all_assignments)}")
    if courses_count is not None:
        report_lines.append(f"**Cursos encontrados:** {courses_count}")
    report_lines.append("")
    report_lines.append("## Cursos explorados")
    report_lines.append("")
    report_lines.append("No aplica (este flujo no obtiene listado de cursos).")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    
    # Separate assignments by status for better reporting
    overdue_assignments = sorted([a for a in assignments if a.get('status') == 'OVERDUE'], key=lambda x: parse_date(x.get('due_date', '')) or datetime.min.date(), reverse=True)
    due_today_assignments = sorted([a for a in assignments if a.get('status') == 'DUE_TODAY'], key=lambda x: parse_date(x.get('due_date', '')) or datetime.max.date())
    upcoming_assignments = sorted([a for a in assignments if a.get('status') == 'UPCOMING'], key=lambda x: parse_date(x.get('due_date', '')) or datetime.max.date())
    
    # Add recently submitted assignments (from all assignments)
    recently_submitted = sorted([a for a in all_assignments if a.get('submission_status', {}).get('submitted') and (a.get('submission_status', {}).get('days_ago') or 999) <= 7], key=lambda x: x.get('submission_status', {}).get('days_ago', 999))
    
    if recently_submitted:
        report_lines.append("## 🚀 Tareas Entregadas Recientemente (Últimos 7 días)")
        report_lines.append("")
        for assignment in recently_submitted:
            report_lines.append(f"- **{assignment.get('title', 'Sin título')}** en **{assignment.get('course', 'Sin curso')}** (Sección: {assignment.get('section', 'N/A')})")
            report_lines.append(f"  - *Estado:* {assignment.get('submission_status', {}).get('status_text', 'N/A')}")
            report_lines.append(f"  - *Fecha de entrega:* {assignment.get('submission_status', {}).get('submission_date', 'N/A')}")
            report_lines.append(f"  - *Archivos adjuntos:* {len(assignment.get('attached_files', []))}")
            report_lines.append(f"  - *URL:* {assignment.get('url', 'N/A')}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")

    if overdue_assignments:
        report_lines.append("## 🔴 Tareas Atrasadas")
        report_lines.append("")
        for assignment in overdue_assignments:
            report_lines.append(f"- **{assignment.get('title', 'Sin título')}** en **{assignment.get('course', 'Sin curso')}** (Sección: {assignment.get('section', 'N/A')})")
            report_lines.append(f"  - *Vencida hace:* {assignment['days_overdue']} días")
            report_lines.append(f"  - *Fecha de vencimiento:* {assignment.get('due_date', 'N/A')}")
            report_lines.append(f"  - *Tipo:* {assignment.get('type', 'N/A')}")
            report_lines.append(f"  - *URL:* {assignment.get('url', 'N/A')}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
    
    if due_today_assignments:
        report_lines.append("## 🔥 Tareas que Vencen Hoy")
        report_lines.append("")
        for assignment in due_today_assignments:
            report_lines.append(f"- **{assignment.get('title', 'Sin título')}** en **{assignment.get('course', 'Sin curso')}** (Sección: {assignment.get('section', 'N/A')})")
            report_lines.append(f"  - *Fecha de vencimiento:* {assignment.get('due_date', 'N/A')}")
            report_lines.append(f"  - *Tipo:* {assignment.get('type', 'N/A')}")
            report_lines.append(f"  - *URL:* {assignment.get('url', 'N/A')}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
    
    if upcoming_assignments:
        report_lines.append("## ⏰ Próximas Tareas")
        report_lines.append("")
        for assignment in upcoming_assignments:
            report_lines.append(f"- **{assignment.get('title', 'Sin título')}** en **{assignment.get('course', 'Sin curso')}** (Sección: {assignment.get('section', 'N/A')})")
            report_lines.append(f"  - *Vence en:* {assignment['days_until_due']} días")
            report_lines.append(f"  - *Fecha de vencimiento:* {assignment.get('due_date', 'N/A')}")
            report_lines.append(f"  - *Tipo:* {assignment.get('type', 'N/A')}")
            report_lines.append(f"  - *URL:* {assignment.get('url', 'N/A')}")
        report_lines.append("")
        report_lines.append("---")
        report_lines.append("")
    
    if not overdue_assignments and not due_today_assignments and not upcoming_assignments and not recently_submitted:
        report_lines.append("## ✅ ¡Excelente noticia!")
        report_lines.append("")
        report_lines.append(f"No se encontraron tareas pendientes o entregadas recientemente para el período consultado.")
        report_lines.append("")
    
    report_lines.append("")
    report_lines.append("*Reporte generado automáticamente por Unisimon Portal Scraper*")
    
    return "\n".join(report_lines)

def generate_empty_report(days_ahead: int, days_behind: int = 0, courses_count: int = None) -> str:
    """
    Generate an empty report when no assignments are found.
    
    Args:
        days_ahead: Number of days ahead that were checked
        days_behind: Number of days behind that were checked
        courses_count: Optional number of courses found (shown in report if provided)
        
    Returns:
        Markdown formatted empty report
    """
    report_lines = []
    
    report_lines.append("# 📚 Reporte de Tareas - Unisimon")
    report_lines.append("")
    report_lines.append(f"**Fecha de generación:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    report_lines.append(f"**Período consultado:** Últimos {days_behind} días y Próximos {days_ahead} días")
    if courses_count is not None:
        report_lines.append(f"**Cursos encontrados:** {courses_count}")
    report_lines.append("")
    report_lines.append("## Cursos explorados")
    report_lines.append("")
    report_lines.append("No aplica (este flujo no obtiene listado de cursos).")
    report_lines.append("")
    report_lines.append("## ✅ ¡Excelente noticia!")
    report_lines.append("")
    report_lines.append(f"No se encontraron tareas pendientes o entregadas recientemente para el período consultado.")
    report_lines.append("")
    report_lines.append("---")
    report_lines.append("")
    report_lines.append("*Reporte generado automáticamente por Unisimon Portal Scraper*")
    
    return "\n".join(report_lines)

def save_report(content: str, filename: str = None, prefix: str = "") -> str:
    """
    Save the markdown report to a file.
    
    Args:
        content: Markdown content to save
        filename: Optional filename (will generate one if not provided)
        prefix: Optional prefix for the filename
        
    Returns:
        Path to the saved file
    """
    # Create output directory if it doesn't exist
    os.makedirs('reports', exist_ok=True)
    
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        prefix_str = f"{prefix}_" if prefix else ""
        filename = f'reports/{prefix_str}assignments_report_{timestamp}.md'
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return filename

def print_debug_info(message: str, debug_mode: bool = True):
    """
    Print debug information if debug mode is enabled.
    
    Args:
        message: Message to print
        debug_mode: Whether debug mode is enabled
    """
    if debug_mode:
        print(f"[DEBUG] {message}")

def save_html_debug(html_content: str, filename: str, debug_mode: bool = True):
    """
    Save HTML content for debugging purposes.
    
    Args:
        html_content: HTML content to save
        filename: Filename to save as
        debug_mode: Whether debug mode is enabled
    """
    if debug_mode:
        os.makedirs('debug_html', exist_ok=True)
        filepath = f'debug_html/{filename}'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[DEBUG] HTML saved to: {filepath}")
