# Unisimon Portal Scraper
# =======================

import requests
from bs4 import BeautifulSoup
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from config import *
from utils import filter_by_date, generate_markdown_report, save_report, print_debug_info, save_html_debug

class UnisimonScraper:
    """Main scraper class for Unisimon portal."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.authenticated = False
        
    def login(self) -> bool:
        """
        Authenticate with the Unisimon portal.
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            print_debug_info("Starting login process...", DEBUG_MODE)
            
            # Get login page
            print_debug_info(f"Fetching login page: {LOGIN_URL}", DEBUG_MODE)
            response = self.session.get(LOGIN_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            if SAVE_HTML_DEBUG:
                save_html_debug(response.text, "login_page.html", DEBUG_MODE)
            
            # Parse login form
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Look for common form field names
            form = soup.find('form')
            if not form:
                print("❌ Error: No login form found on the page")
                return False
            
            # Extract form data
            form_data = {}
            
            # Get all input fields
            inputs = form.find_all('input')
            for input_field in inputs:
                name = input_field.get('name')
                value = input_field.get('value', '')
                if name:
                    form_data[name] = value
            
            # Add credentials
            form_data.update({
                'username': USERNAME,
                'password': PASSWORD,
            })
            
            print_debug_info(f"Form data: {form_data}", DEBUG_MODE)
            
            # Submit login form
            action_url = form.get('action', LOGIN_URL)
            if action_url.startswith('/'):
                action_url = 'https://aulapregrado.unisimon.edu.co' + action_url
            elif not action_url.startswith('http'):
                action_url = LOGIN_URL
            
            print_debug_info(f"Submitting login to: {action_url}", DEBUG_MODE)
            
            login_response = self.session.post(
                action_url, 
                data=form_data, 
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True
            )
            
            if SAVE_HTML_DEBUG:
                save_html_debug(login_response.text, "login_response.html", DEBUG_MODE)
            
            # Check if login was successful
            login_success = self._verify_login_success(login_response)
            print_debug_info(f"Login verification result: {login_success}", DEBUG_MODE)
            
            if login_success:
                self.authenticated = True
                print("Login successful!")
                return True
            else:
                print("Login failed - invalid credentials or portal structure changed")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Network error during login: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error during login: {e}")
            return False
    
    def _verify_login_success(self, response: requests.Response) -> bool:
        """
        Verify if login was successful by checking response content.
        
        Args:
            response: Response from login attempt
            
        Returns:
            True if login appears successful
        """
        # Check for common indicators of successful login
        success_indicators = [
            'dashboard', 'welcome', 'logout', 'profile', 'courses',
            'mis cursos', 'panel', 'inicio', 'home', 'my courses'
        ]
        
        failure_indicators = [
            'invalid credentials', 'login failed', 'usuario o contraseña',
            'entrar al sitio', 'login-index', 'incorrect username',
            'incorrect password', 'authentication failed'
        ]
        
        content_lower = response.text.lower()
        
        print_debug_info(f"Checking URL: {response.url}", DEBUG_MODE)
        print_debug_info(f"Page title contains 'mis cursos': {'mis cursos' in content_lower}", DEBUG_MODE)
        userid_check = 'userid":' in content_lower and '"userid":0' not in content_lower
        print_debug_info(f"User ID check: {userid_check}", DEBUG_MODE)
        
        # Check for failure indicators first
        for indicator in failure_indicators:
            if indicator in content_lower:
                print_debug_info(f"Found failure indicator: {indicator}", DEBUG_MODE)
                return False
        
        # Check for success indicators
        for indicator in success_indicators:
            if indicator in content_lower:
                print_debug_info(f"Found success indicator: {indicator}", DEBUG_MODE)
                return True
        
        # Check if we're no longer on login page
        if 'login' not in response.url.lower() and 'my' in response.url.lower():
            print_debug_info("Success: Not on login page and on 'my' page", DEBUG_MODE)
            return True
        
        # Check for user ID in JavaScript config (Moodle specific)
        if 'userid":' in content_lower and '"userid":0' not in content_lower:
            print_debug_info("Success: User ID found in config", DEBUG_MODE)
            return True
        
        print_debug_info("No success indicators found", DEBUG_MODE)
        return False
    
    def get_assignments(self) -> List[Dict[str, Any]]:
        """
        Extract assignments from all courses.
        
        Returns:
            List of assignment dictionaries
        """
        if not self.authenticated:
            print("Not authenticated. Please login first.")
            return []
        
        try:
            print_debug_info("Starting assignment extraction...", DEBUG_MODE)
            
            # Try to find assignments page
            assignments_urls = self._find_assignments_urls()
            
            all_assignments = []
            
            for url in assignments_urls:
                print_debug_info(f"Checking URL: {url}", DEBUG_MODE)
                assignments = self._extract_assignments_from_url(url)
                all_assignments.extend(assignments)
            
            print_debug_info(f"Found {len(all_assignments)} total assignments", DEBUG_MODE)
            return all_assignments
            
        except Exception as e:
            print(f"Error extracting assignments: {e}")
            return []
    
    def _find_assignments_urls(self) -> List[str]:
        """
        Find URLs that might contain assignments.
        
        Returns:
            List of potential assignment URLs
        """
        urls_to_check = [
            'https://aulapregrado.unisimon.edu.co/',
            'https://aulapregrado.unisimon.edu.co/dashboard/',
            'https://aulapregrado.unisimon.edu.co/courses/',
            'https://aulapregrado.unisimon.edu.co/assignments/',
            'https://aulapregrado.unisimon.edu.co/tareas/',
            'https://aulapregrado.unisimon.edu.co/actividades/',
        ]
        
        # Try to get the main dashboard first
        try:
            response = self.session.get('https://aulapregrado.unisimon.edu.co/', timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for links that might lead to assignments
                links = soup.find_all('a', href=True)
                for link in links:
                    href = link.get('href')
                    text = link.get_text().lower()
                    
                    if any(keyword in text for keyword in ['tarea', 'assignment', 'actividad', 'entrega', 'curso']):
                        if href.startswith('/'):
                            href = 'https://aulapregrado.unisimon.edu.co' + href
                        if href not in urls_to_check:
                            urls_to_check.append(href)
                            
        except Exception as e:
            print_debug_info(f"Error finding additional URLs: {e}", DEBUG_MODE)
        
        return urls_to_check
    
    def _extract_assignments_from_url(self, url: str) -> List[Dict[str, Any]]:
        """
        Extract assignments from a specific URL.
        
        Args:
            url: URL to extract assignments from
            
        Returns:
            List of assignment dictionaries
        """
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                return []
            
            if SAVE_HTML_DEBUG:
                filename = f"page_{url.split('/')[-1] or 'root'}.html"
                save_html_debug(response.text, filename, DEBUG_MODE)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            assignments = []
            
            # Look for common assignment patterns
            assignment_selectors = [
                'div[class*="assignment"]',
                'div[class*="tarea"]',
                'div[class*="activity"]',
                'div[class*="actividad"]',
                'tr[class*="assignment"]',
                'li[class*="assignment"]',
                '.assignment-item',
                '.tarea-item',
                '.activity-item',
            ]
            
            for selector in assignment_selectors:
                elements = soup.select(selector)
                for element in elements:
                    assignment = self._parse_assignment_element(element)
                    if assignment:
                        assignments.append(assignment)
            
            # Also look for table rows that might contain assignments
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:  # At least title and date columns
                        assignment = self._parse_table_row(row)
                        if assignment:
                            assignments.append(assignment)
            
            print_debug_info(f"Found {len(assignments)} assignments at {url}", DEBUG_MODE)
            return assignments
            
        except Exception as e:
            print_debug_info(f"Error extracting from {url}: {e}", DEBUG_MODE)
            return []
    
    def _parse_assignment_element(self, element) -> Optional[Dict[str, Any]]:
        """
        Parse an assignment element to extract information.
        
        Args:
            element: BeautifulSoup element containing assignment info
            
        Returns:
            Assignment dictionary or None if parsing fails
        """
        try:
            assignment = {}
            
            # Try to find title
            title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.name', 'strong', 'b']
            for selector in title_selectors:
                title_elem = element.find(selector)
                if title_elem:
                    assignment['title'] = title_elem.get_text().strip()
                    break
            
            # Try to find due date
            date_selectors = ['.date', '.due-date', '.fecha', '.deadline', 'time']
            for selector in date_selectors:
                date_elem = element.find(selector)
                if date_elem:
                    assignment['due_date'] = date_elem.get_text().strip()
                    break
            
            # Try to find description
            desc_selectors = ['.description', '.desc', '.content', 'p']
            for selector in desc_selectors:
                desc_elem = element.find(selector)
                if desc_elem:
                    assignment['description'] = desc_elem.get_text().strip()
                    break
            
            # Try to find course name
            course_selectors = ['.course', '.curso', '.subject', '.materia']
            for selector in course_selectors:
                course_elem = element.find(selector)
                if course_elem:
                    assignment['course'] = course_elem.get_text().strip()
                    break
            
            # Only return if we found at least a title
            if assignment.get('title'):
                return assignment
            
        except Exception as e:
            print_debug_info(f"Error parsing assignment element: {e}", DEBUG_MODE)
        
        return None
    
    def _parse_table_row(self, row) -> Optional[Dict[str, Any]]:
        """
        Parse a table row that might contain assignment information.
        
        Args:
            row: BeautifulSoup table row element
            
        Returns:
            Assignment dictionary or None if parsing fails
        """
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                return None
            
            assignment = {}
            
            # Assume first cell is title, look for date in other cells
            assignment['title'] = cells[0].get_text().strip()
            
            # Look for date patterns in other cells
            for cell in cells[1:]:
                text = cell.get_text().strip()
                if any(char.isdigit() for char in text) and ('/' in text or '-' in text):
                    assignment['due_date'] = text
                    break
            
            # Look for course name (might be in headers or previous rows)
            parent_table = row.find_parent('table')
            if parent_table:
                headers = parent_table.find_all('th')
                if headers:
                    # Try to find course name in table headers
                    for header in headers:
                        text = header.get_text().strip().lower()
                        if any(keyword in text for keyword in ['curso', 'materia', 'course', 'subject']):
                            assignment['course'] = text
                            break
            
            # Only return if we found at least a title
            if assignment.get('title'):
                return assignment
                
        except Exception as e:
            print_debug_info(f"Error parsing table row: {e}", DEBUG_MODE)
        
        return None
    
    def run(self) -> bool:
        """
        Run the complete scraping process.
        
        Returns:
            True if process completed successfully
        """
        print("Starting Unisimon Portal Scraper...")
        print(f"Checking assignments for the next {DAYS_AHEAD} days")
        print("=" * 50)
        
        # Login
        if not self.login():
            return False
        
        # Extract assignments
        all_assignments = self.get_assignments()
        
        if not all_assignments:
            print("No assignments found. This might be due to:")
            print("   - Portal structure changes")
            print("   - No assignments in the system")
            print("   - Need to use Selenium for JavaScript content")
            print("\nCheck the debug HTML files in 'debug_html/' folder")
            
            # Generate empty report
            report_content = generate_markdown_report([], DAYS_AHEAD)
            filename = save_report(report_content)
            print(f"Empty report saved to: {filename}")
            return True
        
        # Filter assignments by date
        filtered_assignments = filter_by_date(all_assignments, DAYS_AHEAD)
        
        print(f"Found {len(all_assignments)} total assignments")
        print(f"{len(filtered_assignments)} assignments due in the next {DAYS_AHEAD} days")
        
        # Generate and save report
        report_content = generate_markdown_report(filtered_assignments, DAYS_AHEAD)
        filename = save_report(report_content)
        
        print(f"Report saved to: {filename}")
        print("Scraping completed successfully!")
        
        return True

def main():
    """Main function to run the scraper."""
    scraper = UnisimonScraper()
    success = scraper.run()
    
    if not success:
        print("\nScraping failed. Please check the error messages above.")
        print("\nTroubleshooting tips:")
        print("   1. Verify your credentials in config.py")
        print("   2. Check if the portal URL is still correct")
        print("   3. Consider using Selenium if the portal uses JavaScript")
        print("   4. Check the debug HTML files for portal structure changes")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
