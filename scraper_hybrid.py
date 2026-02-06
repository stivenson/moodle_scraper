#!/usr/bin/env python3
"""
Unisimon Portal Scraper - Hybrid Version
Uses Selenium only for login, then BeautifulSoup + spaCy for data extraction
"""

import os
import time
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import spacy
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from config import LOGIN_URL, USERNAME, PASSWORD, DAYS_AHEAD, DAYS_BEHIND, DEBUG_MODE, USER_AGENT
from utils import filter_by_date, parse_date, generate_markdown_report, save_report, print_debug_info

class UnisimonScraperHybrid:
    """
    Hybrid scraper that uses Selenium for login and BeautifulSoup + spaCy for data extraction.
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.driver = None
        self.authenticated = False
        self.nlp = None
        
        # Initialize spaCy model
        try:
            self.nlp = spacy.load("es_core_news_sm")
            print_debug_info("spaCy Spanish model loaded successfully", DEBUG_MODE)
        except OSError:
            print("spaCy Spanish model not found. Installing...")
            os.system("python -m spacy download es_core_news_sm")
            try:
                self.nlp = spacy.load("es_core_news_sm")
                print_debug_info("spaCy Spanish model loaded after installation", DEBUG_MODE)
            except:
                print("Warning: Could not load spaCy model. Using basic text processing.")
                self.nlp = None
    
    def setup_driver(self):
        """Setup Chrome driver with appropriate options."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")  # Run in background
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument(f"--user-agent={USER_AGENT}")
            
            # Disable images and CSS for faster loading
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.managed_default_content_settings.stylesheets": 2
            }
            chrome_options.add_experimental_option("prefs", prefs)
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
            
            print_debug_info("Chrome driver setup successfully", DEBUG_MODE)
            return True
            
        except Exception as e:
            print(f"Error setting up Chrome driver: {e}")
            print("Make sure Chrome is installed and try running: pip install webdriver-manager")
            return False
    
    def login_with_selenium(self) -> bool:
        """
        Authenticate with the Unisimon portal using Selenium.
        After successful login, extract cookies and transfer to requests session.
        """
        if not self.driver:
            return False
        
        try:
            print_debug_info("Starting Selenium login process...", DEBUG_MODE)
            
            # Navigate to login page
            self.driver.get(LOGIN_URL)
            print_debug_info(f"Navigated to: {LOGIN_URL}", DEBUG_MODE)
            
            # Wait for login form to load
            wait = WebDriverWait(self.driver, 10)
            username_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
            password_field = self.driver.find_element(By.ID, "password")
            
            # Clear fields and enter credentials
            username_field.clear()
            username_field.send_keys(USERNAME)
            password_field.clear()
            password_field.send_keys(PASSWORD)
            
            print_debug_info("Credentials entered", DEBUG_MODE)
            
            # Submit form
            login_button = self.driver.find_element(By.ID, "loginbtn")
            login_button.click()
            
            print_debug_info("Login form submitted", DEBUG_MODE)
            
            # Wait for redirect and check if login was successful
            wait.until(lambda driver: "my" in driver.current_url or "login" in driver.current_url)
            
            # Wait a bit more for page to fully load
            time.sleep(3)
            
            current_url = self.driver.current_url
            print_debug_info(f"Current URL after login: {current_url}", DEBUG_MODE)
            
            # Check if we're on the courses page or dashboard
            if "my/courses" in current_url or "my" in current_url:
                # Transfer cookies from Selenium to requests session
                selenium_cookies = self.driver.get_cookies()
                for cookie in selenium_cookies:
                    self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))
                
                self.authenticated = True
                print("Login successful! Cookies transferred to requests session.")
                return True
            elif "loginredirect" in current_url:
                # This might be a redirect after successful login, check if we can access courses
                try:
                    self.driver.get("https://aulapregrado.unisimon.edu.co/my/courses.php")
                    time.sleep(2)
                    if "my/courses" in self.driver.current_url:
                        # Transfer cookies from Selenium to requests session
                        selenium_cookies = self.driver.get_cookies()
                        for cookie in selenium_cookies:
                            self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))
                        
                        self.authenticated = True
                        print("Login successful! Cookies transferred to requests session.")
                        return True
                except:
                    pass
            
            print(f"Login failed - redirected to: {current_url}")
            return False
                
        except Exception as e:
            print(f"Error during login: {e}")
            return False
    
    def get_course_links_with_selenium(self) -> List[Dict[str, str]]:
        """
        Get course links using Selenium to handle dynamic content.
        """
        try:
            # Navigate to courses page with Selenium
            self.driver.get("https://aulapregrado.unisimon.edu.co/my/courses.php")
            
            # Wait for courses to load dynamically
            wait = WebDriverWait(self.driver, 20)
            
            # Wait for the course container to be present
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-region='courses-view']")))
            
            # Wait a bit more for JavaScript to load the courses
            time.sleep(5)
            
            # Look for course links with multiple selectors
            selectors = [
                "a[href*='course/view.php']",
                "a[href*='course/view']",
                ".course-title a",
                ".course-name a",
                ".coursebox a",
                ".course-item a",
                ".course-card a",
                ".card a",
                "[data-course-id] a",
                ".course a"
            ]
            
            course_data = []
            for selector in selectors:
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for link in links:
                        try:
                            href = link.get_attribute("href")
                            text = link.text.strip()
                            
                            if href and "course/view" in href and text and len(text) > 3:
                                course_data.append({
                                    'url': href,
                                    'name': text
                                })
                        except:
                            continue
                    
                    if course_data:
                        break  # If we found courses with this selector, use it
                        
                except Exception as e:
                    print_debug_info(f"Error with selector {selector}: {e}", DEBUG_MODE)
                    continue
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_courses = []
            for course in course_data:
                if course['url'] not in seen_urls:
                    seen_urls.add(course['url'])
                    unique_courses.append(course)
            
            print_debug_info(f"Found {len(unique_courses)} unique courses", DEBUG_MODE)
            return unique_courses
            
        except Exception as e:
            print_debug_info(f"Error getting course links with Selenium: {e}", DEBUG_MODE)
            return []
    
    def extract_assignments_with_spacy(self, course_name: str, course_url: str) -> List[Dict[str, Any]]:
        """
        Extract assignments from a course page using BeautifulSoup + spaCy.
        Now includes navigation through all course tabs/sections.
        """
        assignments = []
        
        try:
            # Get course page content
            response = self.session.get(course_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'lxml')
            
            # First, extract assignments from the main course page
            main_assignments = self._extract_assignments_from_page(soup, course_name, "Main Page")
            assignments.extend(main_assignments)
            
            # Now find and navigate through all course tabs/sections
            tab_assignments = self._extract_assignments_from_tabs(course_url, course_name)
            assignments.extend(tab_assignments)
            
            print_debug_info(f"Found {len(assignments)} total assignments in {course_name} (including all tabs)", DEBUG_MODE)
            
        except Exception as e:
            print_debug_info(f"Error extracting assignments from course {course_name}: {e}", DEBUG_MODE)
        
        return assignments
    
    def _extract_assignments_from_page(self, soup: BeautifulSoup, course_name: str, section_name: str) -> List[Dict[str, Any]]:
        """
        Extract assignments from a specific page/section.
        """
        assignments = []
        
        try:
            # Look for assignment links with multiple selectors
            assignment_selectors = [
                "a[href*='mod/assign']",
                "a[href*='mod/quiz']", 
                "a[href*='mod/workshop']",
                "a[href*='mod/forum']",
                "a[href*='mod/lesson']",
                "a[href*='mod/chat']",
                ".activity-assign a",
                ".activity-quiz a",
                ".activity-workshop a",
                ".activity-forum a",
                ".activity-item a",
                ".modtype_assign a",
                ".modtype_quiz a",
                ".modtype_workshop a",
                ".modtype_forum a"
            ]
            
            assignment_links = []
            for selector in assignment_selectors:
                links = soup.select(selector)
                assignment_links.extend(links)
            
            # Remove duplicates
            assignment_links = list(set(assignment_links))
            print_debug_info(f"Found {len(assignment_links)} assignment links in {section_name}", DEBUG_MODE)
            
            for link in assignment_links:
                try:
                    title = link.get_text(strip=True)
                    if not title or len(title) < 3:  # Skip very short titles
                        continue
                    
                    # Get due date using spaCy for better text analysis
                    due_date = self.extract_due_date_with_spacy(link, soup)
                    
                    # If no date found with spaCy, try additional methods
                    if not due_date:
                        due_date = self.extract_due_date_fallback(link, soup)
                    
                    # Determine assignment type
                    href = link.get('href', '')
                    assignment_type = self.determine_assignment_type(href)
                    
                    # Extract description and requirements using spaCy
                    description, requirements = self.extract_description_with_spacy(link, soup)
                    
                    # Navigate to individual assignment page to get detailed info
                    detailed_info = self.get_assignment_details(href, course_name)
                    
                    assignment = {
                        'title': title,
                        'due_date': due_date,
                        'course': course_name,
                        'description': description,
                        'requirements': requirements,
                        'type': assignment_type,
                        'url': href,
                        'section': section_name,
                        'submission_status': detailed_info.get('submission_status', {}),
                        'detailed_description': detailed_info.get('description', ''),
                        'attached_files': detailed_info.get('attached_files', []),
                        'submission_time': detailed_info.get('submission_time', ''),
                        'grading_status': detailed_info.get('grading_status', '')
                    }
                    
                    assignments.append(assignment)
                    due_date_info = f" (Due: {due_date})" if due_date else " (No due date found)"
                    print_debug_info(f"Found assignment: {title} (Type: {assignment_type}){due_date_info} in {section_name}", DEBUG_MODE)
                    
                except Exception as e:
                    print_debug_info(f"Error processing assignment link: {e}", DEBUG_MODE)
                    continue
                    
        except Exception as e:
            print_debug_info(f"Error extracting assignments from {section_name}: {e}", DEBUG_MODE)
        
        return assignments
    
    def _extract_assignments_from_tabs(self, course_url: str, course_name: str) -> List[Dict[str, Any]]:
        """
        Extract assignments from all course tabs/sections.
        """
        all_assignments = []
        
        try:
            # Get the main course page to find tabs
            response = self.session.get(course_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            # Look for course tabs/sections - multiple possible selectors
            tab_selectors = [
                ".nav-tabs a",
                ".course-tabs a", 
                ".section-tabs a",
                ".tab-content a",
                "a[href*='section']",
                "a[href*='topic']",
                "a[href*='corte']",
                "a[href*='tema']",
                ".course-content a[href*='id=']",
                ".course-section a"
            ]
            
            tab_links = []
            for selector in tab_selectors:
                links = soup.select(selector)
                for link in links:
                    href = link.get('href', '')
                    text = link.get_text(strip=True)
                    # Filter for course-related tabs (not external links)
                    if href and ('section' in href or 'topic' in href or 'corte' in href or 'tema' in href) and text:
                        tab_links.append({
                            'url': href,
                            'name': text
                        })
            
            # Remove duplicates
            seen_urls = set()
            unique_tabs = []
            for tab in tab_links:
                if tab['url'] not in seen_urls:
                    seen_urls.add(tab['url'])
                    unique_tabs.append(tab)
            
            print_debug_info(f"Found {len(unique_tabs)} course tabs in {course_name}", DEBUG_MODE)
            
            # Navigate through each tab
            for tab in unique_tabs[:5]:  # Limit to first 5 tabs to avoid long execution
                try:
                    tab_name = tab['name']
                    tab_url = tab['url']
                    
                    # Make sure URL is absolute
                    if not tab_url.startswith('http'):
                        if tab_url.startswith('/'):
                            tab_url = 'https://aulapregrado.unisimon.edu.co' + tab_url
                        else:
                            tab_url = 'https://aulapregrado.unisimon.edu.co/' + tab_url
                    
                    print_debug_info(f"Exploring tab: {tab_name}", DEBUG_MODE)
                    
                    # Get tab content
                    tab_response = self.session.get(tab_url, timeout=30)
                    tab_response.raise_for_status()
                    tab_soup = BeautifulSoup(tab_response.content, 'lxml')
                    
                    # Extract assignments from this tab
                    tab_assignments = self._extract_assignments_from_page(tab_soup, course_name, tab_name)
                    all_assignments.extend(tab_assignments)
                    
                    # Small delay between requests
                    time.sleep(1)
                    
                except Exception as e:
                    print_debug_info(f"Error processing tab {tab['name']}: {e}", DEBUG_MODE)
                    continue
                    
        except Exception as e:
            print_debug_info(f"Error extracting assignments from tabs: {e}", DEBUG_MODE)
        
        return all_assignments
    
    def check_submission_status(self, link_element, soup) -> dict:
        """
        Check if assignment was submitted recently (last 7 days).
        """
        submission_info = {
            'submitted': False,
            'submission_date': None,
            'status_text': 'No entregada'
        }
        
        try:
            # Look for submission indicators in parent elements
            parent = link_element.parent
            if parent:
                parent_text = parent.get_text(strip=True)
                
                # Look for submission status indicators
                submission_indicators = [
                    r'entregado[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'submitted[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'presentado[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'completado[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'finalizado[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'✓.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'✅.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'completado.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'finalizado.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
                ]
                
                import re
                for pattern in submission_indicators:
                    matches = re.findall(pattern, parent_text, re.IGNORECASE)
                    if matches:
                        submission_date_str = matches[0]
                        submission_date = self.parse_date(submission_date_str)
                        if submission_date:
                            # Check if submission was within last 7 days
                            today = datetime.now().date()
                            days_ago = (today - submission_date).days
                            
                            if days_ago <= 7:
                                submission_info = {
                                    'submitted': True,
                                    'submission_date': submission_date_str,
                                    'status_text': f'Entregada hace {days_ago} días',
                                    'days_ago': days_ago
                                }
                                break
                            else:
                                submission_info = {
                                    'submitted': True,
                                    'submission_date': submission_date_str,
                                    'status_text': f'Entregada hace {days_ago} días',
                                    'days_ago': days_ago
                                }
                                break
                
                # Also look for visual indicators
                visual_indicators = [
                    'entregado', 'submitted', 'completado', 'finalizado',
                    '✓', '✅', 'check', 'done'
                ]
                
                for indicator in visual_indicators:
                    if indicator.lower() in parent_text.lower():
                        # Try to extract date near the indicator
                        import re
                        date_pattern = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
                        dates = re.findall(date_pattern, parent_text)
                        if dates:
                            submission_date_str = dates[0]
                            submission_date = self.parse_date(submission_date_str)
                            if submission_date:
                                today = datetime.now().date()
                                days_ago = (today - submission_date).days
                                
                                submission_info = {
                                    'submitted': True,
                                    'submission_date': submission_date_str,
                                    'status_text': f'Entregada hace {days_ago} días',
                                    'days_ago': days_ago
                                }
                                break
                        else:
                            submission_info = {
                                'submitted': True,
                                'submission_date': 'Fecha no especificada',
                                'status_text': 'Entregada (fecha no especificada)',
                                'days_ago': None
                            }
                            break
            
        except Exception as e:
            print_debug_info(f"Error checking submission status: {e}", DEBUG_MODE)
        
        return submission_info
    
    def get_assignment_details(self, assignment_url: str, course_name: str) -> dict:
        """
        Navigate to individual assignment page to get detailed information.
        """
        detailed_info = {
            'submission_status': {'submitted': False, 'status_text': 'No entregada'},
            'description': '',
            'attached_files': [],
            'submission_time': '',
            'grading_status': ''
        }
        
        try:
            # Make sure URL is absolute
            if not assignment_url.startswith('http'):
                if assignment_url.startswith('/'):
                    assignment_url = 'https://aulapregrado.unisimon.edu.co' + assignment_url
                else:
                    assignment_url = 'https://aulapregrado.unisimon.edu.co/' + assignment_url
            
            print_debug_info(f"Navigating to assignment details: {assignment_url}", DEBUG_MODE)
            
            # Get assignment detail page
            response = self.session.get(assignment_url, timeout=30)
            response.raise_for_status()
            
            detail_soup = BeautifulSoup(response.content, 'lxml')
            
            # Extract detailed description
            description_selectors = [
                '.no-overflow',
                '.description',
                '.content',
                '.assignment-description',
                '[data-region="assignment-description"]'
            ]
            
            for selector in description_selectors:
                desc_elem = detail_soup.select_one(selector)
                if desc_elem:
                    detailed_info['description'] = desc_elem.get_text(strip=True)
                    break
            
            # Extract submission status information
            submission_status = self.extract_submission_status_from_detail_page(detail_soup)
            detailed_info['submission_status'] = submission_status
            
            # Extract grading status
            grading_status = self.extract_grading_status(detail_soup)
            detailed_info['grading_status'] = grading_status
            
            # Extract submission time
            submission_time = self.extract_submission_time(detail_soup)
            detailed_info['submission_time'] = submission_time
            
            # Extract attached files
            attached_files = self.extract_attached_files(detail_soup)
            detailed_info['attached_files'] = attached_files
            
            print_debug_info(f"Assignment details extracted: Status={submission_status.get('status_text', 'Unknown')}, Files={len(attached_files)}", DEBUG_MODE)
            
        except Exception as e:
            print_debug_info(f"Error getting assignment details from {assignment_url}: {e}", DEBUG_MODE)
        
        return detailed_info
    
    def extract_submission_status_from_detail_page(self, soup: BeautifulSoup) -> dict:
        """
        Extract submission status from assignment detail page.
        """
        submission_info = {
            'submitted': False,
            'status_text': 'No entregada',
            'submission_date': None,
            'days_ago': None
        }
        
        try:
            # Look for submission status table
            status_table = soup.select_one('table.generaltable')
            if status_table:
                rows = status_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        if 'estado de la entrega' in label:
                            if 'enviado' in value.lower() or 'submitted' in value.lower():
                                submission_info['submitted'] = True
                                submission_info['status_text'] = value
                        
                        elif 'última modificación' in label or 'last modification' in label:
                            submission_info['submission_date'] = value
                            # Parse date to calculate days ago
                            parsed_date = self.parse_date(value)
                            if parsed_date:
                                today = datetime.now().date()
                                days_ago = (today - parsed_date).days
                                submission_info['days_ago'] = days_ago
                                if days_ago <= 7:
                                    submission_info['status_text'] = f'Entregada hace {days_ago} días'
            
            # Also look for submission status in other elements
            status_indicators = [
                'enviado para calificar',
                'submitted for grading',
                'entregado',
                'submitted',
                'completado',
                'finalizado'
            ]
            
            page_text = soup.get_text().lower()
            for indicator in status_indicators:
                if indicator in page_text:
                    submission_info['submitted'] = True
                    if not submission_info['status_text'] or submission_info['status_text'] == 'No entregada':
                        submission_info['status_text'] = 'Entregada'
                    break
            
        except Exception as e:
            print_debug_info(f"Error extracting submission status: {e}", DEBUG_MODE)
        
        return submission_info
    
    def extract_grading_status(self, soup: BeautifulSoup) -> str:
        """
        Extract grading status from assignment detail page.
        """
        try:
            status_table = soup.select_one('table.generaltable')
            if status_table:
                rows = status_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        if 'estado de la calificación' in label or 'grading status' in label:
                            return value
            
            return 'No especificado'
            
        except Exception as e:
            print_debug_info(f"Error extracting grading status: {e}", DEBUG_MODE)
            return 'Error'
    
    def extract_submission_time(self, soup: BeautifulSoup) -> str:
        """
        Extract submission time information from assignment detail page.
        """
        try:
            status_table = soup.select_one('table.generaltable')
            if status_table:
                rows = status_table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text(strip=True).lower()
                        value = cells[1].get_text(strip=True)
                        
                        if 'tiempo restante' in label or 'time remaining' in label:
                            return value
                        elif 'última modificación' in label or 'last modification' in label:
                            return value
            
            return 'No especificado'
            
        except Exception as e:
            print_debug_info(f"Error extracting submission time: {e}", DEBUG_MODE)
            return 'Error'
    
    def extract_attached_files(self, soup: BeautifulSoup) -> list:
        """
        Extract attached files from assignment detail page.
        """
        attached_files = []
        
        try:
            # Look for submitted files section
            files_section = soup.select_one('#submitted-files, .submitted-files, [data-region="submitted-files"]')
            if files_section:
                file_links = files_section.find_all('a')
                for link in file_links:
                    file_name = link.get_text(strip=True)
                    file_url = link.get('href', '')
                    if file_name and file_url:
                        attached_files.append({
                            'name': file_name,
                            'url': file_url
                        })
            
            # Also look for files in general content
            file_links = soup.select('a[href*="pluginfile.php"], a[href*="mod/assign/view.php"]')
            for link in file_links:
                file_name = link.get_text(strip=True)
                file_url = link.get('href', '')
                if file_name and file_url and any(ext in file_name.lower() for ext in ['.pdf', '.doc', '.docx', '.txt', '.zip']):
                    attached_files.append({
                        'name': file_name,
                        'url': file_url
                    })
            
        except Exception as e:
            print_debug_info(f"Error extracting attached files: {e}", DEBUG_MODE)
        
        return attached_files
    
    def parse_date(self, date_string: str) -> datetime.date:
        """
        Parse various date formats from the portal.
        """
        if not date_string:
            return None
        
        # Clean the date string
        date_string = date_string.strip()
        
        # Skip obviously invalid dates
        if "31-12-1969" in date_string or "1969" in date_string:
            return None
        
        # Spanish month mapping
        spanish_months = {
            'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
            'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
            'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
        }
        
        # Try to parse Spanish dates like "domingo, 7 de septiembre de 2025, 16:27"
        import re
        spanish_date_pattern = r'(\w+),\s*(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})'
        match = re.search(spanish_date_pattern, date_string, re.IGNORECASE)
        if match:
            try:
                day = int(match.group(2))
                month_name = match.group(3).lower()
                year = int(match.group(4))
                
                if month_name in spanish_months:
                    month = int(spanish_months[month_name])
                    parsed_date = datetime(year, month, day).date()
                    # Check if date is reasonable
                    current_year = datetime.now().year
                    if 2020 <= parsed_date.year <= current_year + 2:
                        return parsed_date
            except (ValueError, KeyError):
                pass
        
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
    
    def extract_due_date_with_spacy(self, link_element, soup) -> str:
        """
        Extract due date using spaCy for better text analysis.
        """
        try:
            # Look in parent elements for date information
            parent = link_element.parent
            if parent:
                # Get all text in the parent element
                parent_text = parent.get_text(strip=True)
                
                if self.nlp:
                    # Use spaCy to find dates
                    doc = self.nlp(parent_text)
                    for ent in doc.ents:
                        if ent.label_ in ["DATE", "TIME"]:
                            return ent.text
                
                # Fallback: look for date patterns
                import re
                date_patterns = [
                    r'\d{1,2}/\d{1,2}/\d{4}',
                    r'\d{1,2}-\d{1,2}-\d{4}',
                    r'\d{1,2} de \w+ de \d{4}',
                    r'\d{1,2} \w+ \d{4}',
                    r'\d{1,2}/\d{1,2}/\d{2}',
                    r'\d{1,2}-\d{1,2}-\d{2}',
                    r'vencimiento.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'entrega.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'hasta.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                    r'deadline.*?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
                ]
                
                for pattern in date_patterns:
                    matches = re.findall(pattern, parent_text, re.IGNORECASE)
                    if matches:
                        return matches[0]
            
            # Also look in sibling elements
            try:
                siblings = parent.find_next_siblings()
                for sibling in siblings[:3]:  # Check first 3 siblings
                    sibling_text = sibling.get_text(strip=True)
                    if sibling_text and any(char.isdigit() for char in sibling_text):
                        if self.nlp:
                            doc = self.nlp(sibling_text)
                            for ent in doc.ents:
                                if ent.label_ in ["DATE", "TIME"]:
                                    return ent.text
                        
                        # Look for date patterns in siblings
                        import re
                        date_patterns = [
                            r'\d{1,2}/\d{1,2}/\d{4}',
                            r'\d{1,2}-\d{1,2}-\d{4}',
                            r'\d{1,2} de \w+ de \d{4}',
                            r'\d{1,2} \w+ \d{4}'
                        ]
                        
                        for pattern in date_patterns:
                            matches = re.findall(pattern, sibling_text)
                            if matches:
                                return matches[0]
            except:
                pass
            
            return ""
            
        except Exception as e:
            print_debug_info(f"Error extracting due date: {e}", DEBUG_MODE)
            return ""
    
    def extract_due_date_fallback(self, link_element, soup) -> str:
        """
        Fallback method to extract due dates using multiple approaches.
        """
        try:
            # Method 1: Look for date elements with specific classes
            date_selectors = [
                ".due-date",
                ".deadline", 
                ".date",
                ".activity-dates",
                ".text-muted",
                ".small",
                "[data-date]",
                ".course-content .date",
                ".activity-item .date"
            ]
            
            for selector in date_selectors:
                try:
                    date_elements = soup.select(selector)
                    for date_elem in date_elements:
                        date_text = date_elem.get_text(strip=True)
                        if date_text and any(char.isdigit() for char in date_text):
                            # Check if this date element is near our link
                            if self.is_element_near_link(link_element, date_elem):
                                return date_text
                except:
                    continue
            
            # Method 2: Look in the entire page for dates near assignment titles
            title_text = link_element.get_text(strip=True)
            if title_text:
                # Find all text elements that might contain dates
                all_text_elements = soup.find_all(text=True)
                for text_elem in all_text_elements:
                    text = str(text_elem).strip()
                    if text and any(char.isdigit() for char in text):
                        # Check if this text contains a date pattern
                        import re
                        date_patterns = [
                            r'\d{1,2}/\d{1,2}/\d{4}',
                            r'\d{1,2}-\d{1,2}-\d{4}',
                            r'\d{1,2} de \w+ de \d{4}',
                            r'\d{1,2} \w+ \d{4}'
                        ]
                        
                        for pattern in date_patterns:
                            matches = re.findall(pattern, text)
                            if matches:
                                # Check if this date is contextually related to our assignment
                                if self.is_date_contextually_related(text, title_text):
                                    return matches[0]
            
            return ""
            
        except Exception as e:
            print_debug_info(f"Error in fallback date extraction: {e}", DEBUG_MODE)
            return ""
    
    def is_element_near_link(self, link_element, date_element) -> bool:
        """
        Check if a date element is near the link element in the DOM.
        """
        try:
            # Check if date element is a sibling or nearby
            link_parent = link_element.parent
            date_parent = date_element.parent
            
            # Same parent
            if link_parent == date_parent:
                return True
            
            # Check if they're siblings
            if link_parent and date_parent:
                if link_parent.parent == date_parent.parent:
                    return True
            
            return False
        except:
            return False
    
    def is_date_contextually_related(self, date_text, title_text) -> bool:
        """
        Check if a date text is contextually related to an assignment title.
        """
        try:
            # Simple heuristic: if the date text contains assignment-related keywords
            assignment_keywords = [
                'entrega', 'vencimiento', 'deadline', 'due', 'fecha',
                'assignment', 'tarea', 'quiz', 'examen', 'foro'
            ]
            
            date_lower = date_text.lower()
            title_lower = title_text.lower()
            
            # Check if date text contains assignment keywords
            for keyword in assignment_keywords:
                if keyword in date_lower:
                    return True
            
            # Check if title contains assignment keywords and date is nearby
            for keyword in assignment_keywords:
                if keyword in title_lower:
                    return True
            
            return False
        except:
            return False
    
    def determine_assignment_type(self, href: str) -> str:
        """
        Determine assignment type based on URL.
        """
        if 'assign' in href:
            return 'Assignment'
        elif 'quiz' in href:
            return 'Quiz'
        elif 'workshop' in href:
            return 'Workshop'
        elif 'forum' in href:
            return 'Forum'
        elif 'lesson' in href:
            return 'Lesson'
        else:
            return 'Activity'
    
    def extract_description_with_spacy(self, link_element, soup) -> tuple:
        """
        Extract description and requirements using spaCy.
        """
        description = ""
        requirements = ""
        
        try:
            # Look for description in nearby elements
            parent = link_element.parent
            if parent:
                # Get text from sibling elements
                siblings = parent.find_next_siblings()
                for sibling in siblings[:3]:  # Check first 3 siblings
                    text = sibling.get_text(strip=True)
                    if text and len(text) > 10:
                        if self.nlp:
                            doc = self.nlp(text)
                            # Look for sentences that might be descriptions
                            for sent in doc.sents:
                                if any(word in sent.text.lower() for word in ['descripción', 'description', 'instrucciones', 'instructions']):
                                    description = sent.text
                                    break
                        else:
                            # Fallback: use first meaningful text
                            if not description:
                                description = text[:200] + "..." if len(text) > 200 else text
            
            return description, requirements
            
        except Exception as e:
            print_debug_info(f"Error extracting description: {e}", DEBUG_MODE)
            return "", ""
    
    def get_assignments(self) -> List[Dict[str, Any]]:
        """
        Extract assignments from all courses using the hybrid approach.
        """
        if not self.authenticated:
            print("Not authenticated. Please login first.")
            return []
        
        try:
            print_debug_info("Starting hybrid assignment extraction...", DEBUG_MODE)
            
            # Get course links using Selenium (for dynamic content)
            courses = self.get_course_links_with_selenium()
            print_debug_info(f"Found {len(courses)} courses to process", DEBUG_MODE)
            
            # Limit to first 5 courses to avoid long execution times
            courses = courses[:5]
            print_debug_info(f"Processing first {len(courses)} courses", DEBUG_MODE)
            
            all_assignments = []
            
            # Process each course
            for i, course in enumerate(courses):
                try:
                    course_url = course['url']
                    course_name = course['name']
                    
                    print_debug_info(f"Processing course {i+1}/{len(courses)}: {course_name}", DEBUG_MODE)
                    
                    # Extract assignments using BeautifulSoup + spaCy
                    assignments = self.extract_assignments_with_spacy(course_name, course_url)
                    all_assignments.extend(assignments)
                    
                    print_debug_info(f"Found {len(assignments)} assignments in {course_name}", DEBUG_MODE)
                    
                    # Add a small delay between courses to be respectful
                    time.sleep(1)
                    
                except Exception as e:
                    print_debug_info(f"Error processing course {course_name}: {e}", DEBUG_MODE)
                    continue
            
            print_debug_info(f"Found {len(all_assignments)} total assignments", DEBUG_MODE)
            return all_assignments
            
        except Exception as e:
            print(f"Error extracting assignments: {e}")
            return []
    
    def run(self) -> bool:
        """
        Run the complete hybrid scraping process.
        """
        print("Starting Unisimon Portal Scraper (Hybrid Version)...")
        print(f"Checking assignments from {DAYS_BEHIND} days ago to {DAYS_AHEAD} days ahead")
        print("=" * 50)
        
        # Setup Selenium driver
        if not self.setup_driver():
            print("Selenium WebDriver not initialized. Exiting.")
            return False
        
        try:
            # Login with Selenium
            if not self.login_with_selenium():
                return False
            
            # Extract assignments using requests + BeautifulSoup + spaCy
            all_assignments = self.get_assignments()
            
            if not all_assignments:
                print("No assignments found. This might be due to:")
                print("   - Portal structure changes")
                print("   - No assignments in the system")
                print("   - Authentication issues")
                
                # Generate empty report
                report_content = generate_markdown_report([], DAYS_AHEAD, DAYS_BEHIND)
                filename = save_report(report_content)
                print(f"Empty report saved to: {filename}")
                return True
            
            # Filter assignments by date (overdue and upcoming)
            filtered_assignments = filter_by_date(all_assignments, DAYS_AHEAD, DAYS_BEHIND)
            
            # Filter recently submitted assignments (last 7 days)
            recently_submitted = [a for a in all_assignments if a.get('submission_status', {}).get('submitted', False) and (a.get('submission_status', {}).get('days_ago') or 999) <= 7]
            
            # Count assignments by status
            overdue_count = len([a for a in filtered_assignments if a.get('status') == 'OVERDUE'])
            due_today_count = len([a for a in filtered_assignments if a.get('status') == 'DUE_TODAY'])
            upcoming_count = len([a for a in filtered_assignments if a.get('status') == 'UPCOMING'])
            submitted_count = len(recently_submitted)
            
            print(f"Found {len(all_assignments)} total assignments")
            print(f"Filtered assignments: {len(filtered_assignments)}")
            print(f"  - Atrasadas: {overdue_count}")
            print(f"  - Vencen hoy: {due_today_count}")
            print(f"  - Proximas: {upcoming_count}")
            print(f"  - Presentadas recientemente: {submitted_count}")
            
            # Generate and save report with filtered assignments and all assignments for recently submitted
            report_content = generate_markdown_report(filtered_assignments, DAYS_AHEAD, DAYS_BEHIND, all_assignments)
            filename = save_report(report_content)
            
            print(f"Report saved to: {filename}")
            print("Scraping completed successfully!")
            
            return True
            
        finally:
            # Clean up
            if self.driver:
                self.driver.quit()
                print_debug_info("Chrome driver closed", DEBUG_MODE)

def main():
    """Main function to run the hybrid scraper."""
    scraper = UnisimonScraperHybrid()
    success = scraper.run()
    
    if not success:
        print("\nScraping failed. Please check the error messages above.")
        print("\nTroubleshooting tips:")
        print("   1. Verify your credentials in config.py")
        print("   2. Check if the portal URL is still correct")
        print("   3. Ensure your Chrome browser is up to date")
        print("   4. Install spaCy Spanish model: python -m spacy download es_core_news_sm")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
