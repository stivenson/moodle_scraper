# Test script for Unisimon Portal Scraper
# =======================================

"""
Simple test script to verify the scraper implementation.
This script tests the utility functions without making actual HTTP requests.
"""

from utils import filter_by_date, parse_date, generate_markdown_report
from datetime import datetime, timedelta

def test_date_parsing():
    """Test date parsing functionality."""
    print("Testing date parsing...")
    
    test_dates = [
        "2024-01-15",
        "15/01/2024", 
        "15-01-2024",
        "January 15, 2024",
        "15 January 2024",
        "2024-01-15 14:30:00",
        "15/01/2024 14:30",
        "invalid date",
        "",
        None
    ]
    
    for date_str in test_dates:
        parsed = parse_date(date_str)
        print(f"  '{date_str}' -> {parsed}")
    
    print("Date parsing test completed\n")

def test_date_filtering():
    """Test assignment filtering by date."""
    print("Testing date filtering...")
    
    # Create test assignments
    today = datetime.now().date()
    assignments = [
        {
            'title': 'Assignment 1',
            'due_date': (today + timedelta(days=5)).strftime('%Y-%m-%d'),
            'course': 'Test Course 1'
        },
        {
            'title': 'Assignment 2', 
            'due_date': (today + timedelta(days=15)).strftime('%Y-%m-%d'),
            'course': 'Test Course 1'
        },
        {
            'title': 'Assignment 3',
            'due_date': (today + timedelta(days=25)).strftime('%Y-%m-%d'),
            'course': 'Test Course 2'
        },
        {
            'title': 'Assignment 4',
            'due_date': (today - timedelta(days=5)).strftime('%Y-%m-%d'),  # Past date
            'course': 'Test Course 2'
        }
    ]
    
    # Test with 21 days ahead
    filtered = filter_by_date(assignments, 21)
    print(f"  Total assignments: {len(assignments)}")
    print(f"  Filtered (21 days): {len(filtered)}")
    
    for assignment in filtered:
        print(f"    - {assignment['title']} (due: {assignment['due_date']})")
    
    print("Date filtering test completed\n")

def test_markdown_generation():
    """Test markdown report generation."""
    print("Testing markdown generation...")
    
    # Create test assignments
    today = datetime.now().date()
    assignments = [
        {
            'title': 'Tarea de Matemáticas',
            'due_date': (today + timedelta(days=3)).strftime('%Y-%m-%d'),
            'course': 'Matemáticas Básicas',
            'description': 'Resolver ejercicios de álgebra',
            'requirements': 'Entregar en formato PDF'
        },
        {
            'title': 'Proyecto de Programación',
            'due_date': (today + timedelta(days=10)).strftime('%Y-%m-%d'),
            'course': 'Programación I',
            'description': 'Implementar un sistema de gestión',
            'requirements': 'Código en Python, documentación incluida'
        }
    ]
    
    # Generate report
    report = generate_markdown_report(assignments, 21)
    
    # Save test report
    with open('test_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"  Generated report with {len(assignments)} assignments")
    print(f"  Report saved to: test_report.md")
    print("Markdown generation test completed\n")

def test_empty_report():
    """Test empty report generation."""
    print("Testing empty report generation...")
    
    report = generate_markdown_report([], 21)
    
    with open('test_empty_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("  Generated empty report")
    print("  Report saved to: test_empty_report.md")
    print("Empty report test completed\n")

def main():
    """Run all tests."""
    print("Running Unisimon Scraper Tests")
    print("=" * 40)
    
    try:
        test_date_parsing()
        test_date_filtering()
        test_markdown_generation()
        test_empty_report()
        
        print("All tests completed successfully!")
        print("\nGenerated files:")
        print("  - test_report.md")
        print("  - test_empty_report.md")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
