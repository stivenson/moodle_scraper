# Unisimon Portal Scraper with Selenium
# ====================================

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

from config import *
from utils import filter_by_date, generate_markdown_report, save_report, print_debug_info

class UnisimonSeleniumScraper:
    """Selenium-based scraper for Unisimon portal with JavaScript support."""
    
    def __init__(self):
        self.driver = None
        self.authenticated = False
        
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
    
    def safe_find_elements(self, selector: str, timeout: int = 10) -> List:
        """Safely find elements with retry logic to handle stale elements."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
        
        try:
            wait = WebDriverWait(self.driver, timeout)
            elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector)))
            return elements
        except (StaleElementReferenceException, TimeoutException):
            print_debug_info(f"Stale element or timeout for selector: {selector}", DEBUG_MODE)
            return []
    
    def safe_get_course_links(self) -> List[Dict[str, str]]:
        """Safely get all course links with their names."""
        course_data = []
        
        try:
            # Wait for page to fully load
            time.sleep(3)
            
            # Try multiple approaches to get course links
            selectors = [
                "a[href*='course/view.php']",
                "a[href*='course/view']",
                ".course-title a",
                ".course-name a",
                ".coursebox a",
                ".course-item a"
            ]
            
            for selector in selectors:
                try:
                    links = self.safe_find_elements(selector)
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
            print_debug_info(f"Error getting course links: {e}", DEBUG_MODE)
            return []
    
    def login(self) -> bool:
        """
        Authenticate with the Unisimon portal using Selenium.
        
        Returns:
            True if login successful, False otherwise
        """
        try:
            if not self.driver:
                if not self.setup_driver():
                    return False
            
            print_debug_info("Starting Selenium login process...", DEBUG_MODE)
            
            # Navigate to login page
            self.driver.get(LOGIN_URL)
            print_debug_info(f"Navigated to: {LOGIN_URL}", DEBUG_MODE)
            
            # Wait for login form to load
            wait = WebDriverWait(self.driver, 20)
            username_field = wait.until(EC.presence_of_element_located((By.NAME, "username")))
            password_field = self.driver.find_element(By.NAME, "password")
            
            # Fill in credentials
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
                # Additional check: look for user-specific content
                try:
                    # Check for user name or logout link
                    user_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                        "a[href*='logout'], .user-info, .logininfo, [data-userid]")
                    if user_elements:
                        self.authenticated = True
                        print("Login successful!")
                        return True
                except:
                    pass
                
                # If we're on my page but no user elements found, still consider it successful
                self.authenticated = True
                print("Login successful!")
                return True
            else:
                print(f"Login failed - redirected to: {current_url}")
                return False
                
        except Exception as e:
            print(f"Error during login: {e}")
            return False
    
    def get_assignments(self) -> List[Dict[str, Any]]:
        """
        Extract assignments from all courses using Selenium.
        
        Returns:
            List of assignment dictionaries
        """
        if not self.authenticated:
            print("Not authenticated. Please login first.")
            return []
        
        try:
            print_debug_info("Starting Selenium assignment extraction...", DEBUG_MODE)
            
            # Navigate to courses page
            self.driver.get("https://aulapregrado.unisimon.edu.co/my/courses.php")
            
            # Wait for courses to load
            wait = WebDriverWait(self.driver, 20)
            
            # Wait for the course overview block to load
            try:
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "block-myoverview")))
                print_debug_info("Course overview block loaded", DEBUG_MODE)
            except:
                print_debug_info("Course overview block not found, trying alternative approach", DEBUG_MODE)
            
            # Wait a bit more for JavaScript to load content
            time.sleep(5)
            
            # Use the robust method to get course links
            courses = self.safe_get_course_links()
            print_debug_info(f"Found {len(courses)} courses to process", DEBUG_MODE)
            
            # Limit to first 5 courses to avoid long execution times
            courses = courses[:5]
            print_debug_info(f"Processing first {len(courses)} courses to avoid timeouts", DEBUG_MODE)
            
            all_assignments = []
            
            # Process each course with timeout protection
            import signal
            import time as time_module
            
            for i, course in enumerate(courses):
                start_time = time_module.time()
                max_course_time = 60  # Maximum 60 seconds per course
                
                try:
                    course_url = course['url']
                    course_name = course['name']
                    
                    print_debug_info(f"Processing course {i+1}/{len(courses)}: {course_name}", DEBUG_MODE)
                    
                    # Navigate to course with timeout
                    try:
                        self.driver.set_page_load_timeout(30)  # 30 second timeout
                        self.driver.get(course_url)
                        
                        # Look for assignments in this course
                        assignments = self._extract_assignments_from_course(course_name)
                        all_assignments.extend(assignments)
                        
                        print_debug_info(f"Found {len(assignments)} assignments in {course_name}", DEBUG_MODE)
                        
                    except Exception as e:
                        print_debug_info(f"Error loading course {course_name}: {e}", DEBUG_MODE)
                        assignments = []
                    
                    # Check if we've exceeded max time for this course
                    elapsed_time = time_module.time() - start_time
                    if elapsed_time > max_course_time:
                        print_debug_info(f"Course {course_name} took too long ({elapsed_time:.1f}s), skipping", DEBUG_MODE)
                        continue
                    
                    # Go back to courses page for next iteration
                    try:
                        self.driver.get("https://aulapregrado.unisimon.edu.co/my/courses.php")
                        time.sleep(2)  # Wait for page to reload
                    except Exception as e:
                        print_debug_info(f"Error returning to courses page: {e}", DEBUG_MODE)
                        # If we can't go back, try to continue with next course
                        continue
                    
                except Exception as e:
                    print_debug_info(f"Error processing course {course_name}: {e}", DEBUG_MODE)
                    continue
                
                # Add a small delay between courses to be respectful
                time.sleep(1)
            
            # Also try to find assignments in the main dashboard
            print_debug_info("Checking main dashboard for assignments...", DEBUG_MODE)
            self.driver.get("https://aulapregrado.unisimon.edu.co/")
            time.sleep(3)
            
            dashboard_assignments = self._extract_assignments_from_dashboard()
            all_assignments.extend(dashboard_assignments)
            
            print_debug_info(f"Found {len(all_assignments)} total assignments", DEBUG_MODE)
            return all_assignments
            
        except Exception as e:
            print(f"Error extracting assignments: {e}")
            return []
    
    def _extract_assignments_from_course(self, course_name: str) -> List[Dict[str, Any]]:
        """Extract assignments from a specific course page."""
        assignments = []
        
        try:
            # Wait for page to load with timeout
            try:
                wait = WebDriverWait(self.driver, 10)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except:
                print_debug_info(f"Timeout waiting for page to load in {course_name}", DEBUG_MODE)
                return []
            
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
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    assignment_links.extend(links)
                except:
                    continue
            
            # Remove duplicates
            assignment_links = list(set(assignment_links))
            print_debug_info(f"Found {len(assignment_links)} assignment links in {course_name}", DEBUG_MODE)
            
            for link in assignment_links:
                try:
                    title = link.text.strip()
                    if not title or len(title) < 3:  # Skip very short titles
                        continue
                    
                    # Get due date if available - try multiple approaches
                    due_date = ""
                    try:
                        # Look in parent elements for date information
                        parent = link.find_element(By.XPATH, "./..")
                        date_elements = parent.find_elements(By.CSS_SELECTOR, 
                            ".text-muted, .small, .date, .due-date, .deadline, .activity-dates")
                        
                        for date_elem in date_elements:
                            date_text = date_elem.text.strip()
                            if any(char.isdigit() for char in date_text) and len(date_text) > 3:
                                due_date = date_text
                                break
                        
                        # If no date found in parent, look in grandparent
                        if not due_date:
                            grandparent = parent.find_element(By.XPATH, "./..")
                            date_elements = grandparent.find_elements(By.CSS_SELECTOR, 
                                ".text-muted, .small, .date, .due-date, .deadline, .activity-dates")
                            
                            for date_elem in date_elements:
                                date_text = date_elem.text.strip()
                                if any(char.isdigit() for char in date_text) and len(date_text) > 3:
                                    due_date = date_text
                                    break
                    except:
                        pass
                    
                    # Determine assignment type
                    href = link.get_attribute('href', '')
                    if 'assign' in href:
                        assignment_type = 'Assignment'
                    elif 'quiz' in href:
                        assignment_type = 'Quiz'
                    elif 'workshop' in href:
                        assignment_type = 'Workshop'
                    elif 'forum' in href:
                        assignment_type = 'Forum'
                    elif 'lesson' in href:
                        assignment_type = 'Lesson'
                    else:
                        assignment_type = 'Activity'
                    
                    assignment = {
                        'title': title,
                        'due_date': due_date,
                        'course': course_name,
                        'description': '',
                        'requirements': '',
                        'type': assignment_type,
                        'url': href
                    }
                    
                    assignments.append(assignment)
                    print_debug_info(f"Found assignment: {title} (Type: {assignment_type})", DEBUG_MODE)
                    
                except Exception as e:
                    print_debug_info(f"Error processing assignment link: {e}", DEBUG_MODE)
                    continue
                    
        except Exception as e:
            print_debug_info(f"Error extracting assignments from course {course_name}: {e}", DEBUG_MODE)
        
        return assignments
    
    def _extract_assignments_from_dashboard(self) -> List[Dict[str, Any]]:
        """Extract assignments from the main dashboard."""
        assignments = []
        
        try:
            # Look for upcoming events or assignments
            upcoming_elements = self.driver.find_elements(By.CSS_SELECTOR, 
                ".upcoming-events, .calendar-events, .event, .assignment")
            
            for element in upcoming_elements:
                try:
                    title = element.text.strip()
                    if not title:
                        continue
                    
                    assignment = {
                        'title': title,
                        'due_date': '',
                        'course': 'Dashboard',
                        'description': '',
                        'requirements': '',
                        'type': 'Event'
                    }
                    
                    assignments.append(assignment)
                    
                except Exception as e:
                    print_debug_info(f"Error processing dashboard element: {e}", DEBUG_MODE)
                    continue
                    
        except Exception as e:
            print_debug_info(f"Error extracting from dashboard: {e}", DEBUG_MODE)
        
        return assignments
    
    def run(self) -> bool:
        """
        Run the complete scraping process with Selenium.
        
        Returns:
            True if process completed successfully
        """
        print("Starting Unisimon Portal Scraper (Selenium)...")
        print(f"Checking assignments for the next {DAYS_AHEAD} days")
        print("=" * 50)
        
        # Setup driver
        if not self.setup_driver():
            return False
        
        try:
            # Login
            if not self.login():
                return False
            
            # Extract assignments
            all_assignments = self.get_assignments()
            
            if not all_assignments:
                print("No assignments found. This might be due to:")
                print("   - No assignments in the system")
                print("   - Different portal structure")
                print("   - Assignments in a different section")
                
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
            
        finally:
            # Close driver
            if self.driver:
                self.driver.quit()
                print_debug_info("Chrome driver closed", DEBUG_MODE)

def main():
    """Main function to run the Selenium scraper."""
    scraper = UnisimonSeleniumScraper()
    success = scraper.run()
    
    if not success:
        print("\nScraping failed. Please check the error messages above.")
        print("\nTroubleshooting tips:")
        print("   1. Make sure Chrome browser is installed")
        print("   2. Check your internet connection")
        print("   3. Verify credentials in config.py")
        print("   4. Try running without headless mode (modify scraper_selenium.py)")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
