#!/usr/bin/env python3
"""
Fix tests to wait for alerts table before accessing settings
"""

import re

def fix_multi_sort_wait_for_table():
    """Update test_multi_sort_asc_dsc to wait for table before settings"""
    file_path = "/workspace/tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py"
    
    print("Fixing test_multi_sort_asc_dsc to wait for table...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the pattern where we try to click settings button
    pattern = r'(browser\.goto\(f"\{KEEP_UI_URL\}/alerts/feed\?cel=\{cel_to_filter_alerts\}"\))([\s\S]*?)(try:\s+expect\([\s\S]*?browser\.locator\("\[data-testid=\'alerts-table\'\] table tbody tr"\))'
    
    replacement = r'''\1
    # Wait for the page to load and alerts table to be visible
    browser.wait_for_load_state("networkidle")
    browser.wait_for_selector("[data-testid='alerts-table']", timeout=10000)
    browser.wait_for_timeout(2000)  # Give UI time to fully render\2\3'''
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print("✅ Fixed test_multi_sort_asc_dsc table wait")
        return True
    return False

def fix_backend_column_test_wait():
    """Update test_backend_column_configuration_persistence to wait properly"""
    file_path = "/workspace/tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py"
    
    print("Fixing test_backend_column_configuration_persistence wait conditions...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find where settings button is clicked
    pattern = r'(# Configure columns in the preset\s+)(settings_button = browser\.locator\("\[data-testid=\'settings-button\'\]"\))'
    
    replacement = r'''\1# Wait for table to be fully rendered before accessing settings
        browser.wait_for_selector("[data-testid='alerts-table']", timeout=10000)
        browser.wait_for_timeout(1000)
        
        \2'''
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print("✅ Fixed test_backend_column_configuration_persistence wait")
        return True
    return False

def fix_theme_test_table_wait():
    """Update test_theme to wait for table before settings"""
    file_path = "/workspace/tests/e2e_tests/test_end_to_end_theme.py"
    
    print("Fixing test_theme to wait for table...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Add wait for table after the test alerts button click
    pattern = r'(# Click test alerts button using data-testid[\s\S]*?)\n(\s+# open the settings modal)'
    
    replacement = r'''\1
        
        # Wait for alerts table to be rendered
        page.wait_for_selector("[data-testid='alerts-table']", timeout=10000, state="visible")
        page.wait_for_timeout(1000)  # Give UI time to stabilize

\2'''
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print("✅ Fixed test_theme table wait")
        return True
    return False

def main():
    """Main function to fix all test table wait issues"""
    print("🔧 Fixing tests to wait for alerts table...\n")
    
    changes_made = []
    
    if fix_multi_sort_wait_for_table():
        changes_made.append("test_multi_sort_asc_dsc")
    
    if fix_backend_column_test_wait():
        changes_made.append("test_backend_column_configuration_persistence")
        
    if fix_theme_test_table_wait():
        changes_made.append("test_theme")
    
    if changes_made:
        print(f"\n✅ Fixed {len(changes_made)} tests: {', '.join(changes_made)}")
    else:
        print("\n⚠️  No additional fixes were needed")

if __name__ == "__main__":
    main()