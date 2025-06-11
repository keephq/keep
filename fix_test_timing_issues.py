#!/usr/bin/env python3
"""
Fix timing issues in E2E tests by adding proper wait conditions
"""

import os
import re

def fix_test_multi_sort():
    """Fix the test_multi_sort_asc_dsc test"""
    file_path = "/workspace/tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py"
    
    print("Fixing test_multi_sort_asc_dsc...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the test_multi_sort_asc_dsc function
    pattern = r'(def test_multi_sort_asc_dsc\([\s\S]*?)browser\.locator\("\[data-testid=\'settings-button\'\]"\)\.click\(\)'
    
    replacement = r'\1# Wait for the page to fully load and settings button to be visible\n        browser.wait_for_load_state("networkidle")\n        browser.wait_for_timeout(2000)\n        settings_button = browser.locator("[data-testid=\'settings-button\']")\n        expect(settings_button).to_be_visible(timeout=10000)\n        settings_button.click()'
    
    new_content = re.sub(pattern, replacement, content)
    
    # Also add a wait after clicking the settings button
    pattern2 = r'(settings_button\.click\(\))\n(\s+settings_panel_locator = browser\.locator\("\[data-testid=\'settings-panel\'\]"\))'
    replacement2 = r'\1\n        # Wait for settings panel to appear\n        browser.wait_for_timeout(1000)\n\2\n        expect(settings_panel_locator).to_be_visible(timeout=10000)'
    
    new_content = re.sub(pattern2, replacement2, new_content)
    
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print("✅ Fixed test_multi_sort_asc_dsc")
    else:
        print("⚠️  No changes made to test_multi_sort_asc_dsc")

def fix_test_backend_column_config():
    """Fix the test_backend_column_configuration_persistence test"""
    file_path = "/workspace/tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py"
    
    print("Fixing test_backend_column_configuration_persistence...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find where we navigate to the preset and add better waits
    pattern = r'(browser\.goto\(f"\{KEEP_UI_URL\}/alerts/\{test_preset_name\}"\))\n(\s+browser\.wait_for_load_state\("networkidle"\))\n(\s+browser\.wait_for_timeout\(2000\))'
    
    replacement = r'\1\n\2\n\3\n        # Wait for alerts table to be fully loaded\n        browser.wait_for_selector("[data-testid=\'alerts-table\']", timeout=10000)\n        browser.wait_for_selector("[data-testid=\'facets-panel\']", timeout=10000)'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print("✅ Fixed test_backend_column_configuration_persistence")
    else:
        print("⚠️  No changes made to test_backend_column_configuration_persistence")

def fix_test_theme():
    """Fix the test_theme test"""
    file_path = "/workspace/tests/e2e_tests/test_end_to_end_theme.py"
    
    print("Fixing test_theme...")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace the problematic settings button click section
    pattern = r'# open the settings modal using data-testid\s+try:\s+page\.locator\(\'\[data-testid="settings-button"\]\'\)\.click\(\)[\s\S]*?page\.locator\("button:has\(svg\)"\)\.nth\(0\)\.click\(\)'
    
    replacement = '''# open the settings modal using data-testid
        # Wait for alerts table to be loaded first
        page.wait_for_selector("[data-testid='alerts-table']", timeout=10000)
        
        # Now wait for and click the settings button
        settings_button = page.locator('[data-testid="settings-button"]')
        settings_button.wait_for(state="visible", timeout=10000)
        settings_button.click()'''
    
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if new_content != content:
        with open(file_path, 'w') as f:
            f.write(new_content)
        print("✅ Fixed test_theme")
    else:
        print("⚠️  No changes made to test_theme")

def add_import_if_missing(file_path, import_line):
    """Add an import if it's missing from the file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    if import_line not in content:
        # Find the last import line
        import_pattern = r'((?:from|import) .+\n)+'
        match = re.search(import_pattern, content)
        if match:
            end_pos = match.end()
            new_content = content[:end_pos] + import_line + '\n' + content[end_pos:]
            with open(file_path, 'w') as f:
                f.write(new_content)
            return True
    return False

def ensure_expect_import():
    """Ensure expect is imported in test files"""
    files_to_check = [
        "/workspace/tests/e2e_tests/incidents_alerts_tests/test_filtering_sort_search_on_alerts.py",
        "/workspace/tests/e2e_tests/test_end_to_end_theme.py"
    ]
    
    for file_path in files_to_check:
        if os.path.exists(file_path):
            if add_import_if_missing(file_path, "from playwright.sync_api import expect"):
                print(f"✅ Added expect import to {os.path.basename(file_path)}")

def main():
    """Main function to fix all test timing issues"""
    print("🔧 Fixing E2E test timing issues...")
    
    # First ensure necessary imports
    ensure_expect_import()
    
    # Fix individual tests
    fix_test_multi_sort()
    fix_test_backend_column_config()
    fix_test_theme()
    
    print("\n✅ Test timing fixes applied!")

if __name__ == "__main__":
    main()