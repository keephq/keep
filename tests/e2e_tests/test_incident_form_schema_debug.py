"""
Debug test to understand the incident creation UI
"""

import os
import time
from playwright.sync_api import Page, expect
from tests.e2e_tests.utils import init_e2e_test, save_failure_artifacts, setup_console_listener


def test_debug_incident_creation_ui(browser: Page):
    """Debug test to understand how incident creation works"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)
    
    try:
        # Navigate to incidents page
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(2000)
        
        # Take screenshot of initial page
        browser.screenshot(path="debug_1_incidents_page.png")
        print("Screenshot saved: debug_1_incidents_page.png")
        
        # Find and click create button
        create_button = browser.locator("button").filter(has_text="create").first
        if create_button.is_visible():
            print(f"Found create button with text: {create_button.inner_text()}")
            create_button.click()
            
            # Wait a bit for any animation/modal
            browser.wait_for_timeout(2000)
            
            # Take screenshot after clicking
            browser.screenshot(path="debug_2_after_create_click.png")
            print("Screenshot saved: debug_2_after_create_click.png")
            
            # Check for any dialogs
            dialogs = browser.locator("[role='dialog']")
            print(f"Found {dialogs.count()} dialog(s)")
            
            if dialogs.count() > 0:
                # Check visibility of first dialog
                first_dialog = dialogs.first
                is_visible = first_dialog.is_visible()
                print(f"First dialog visible: {is_visible}")
                
                if not is_visible:
                    # Try to get computed style
                    opacity = browser.evaluate("el => window.getComputedStyle(el).opacity", first_dialog.element_handle())
                    display = browser.evaluate("el => window.getComputedStyle(el).display", first_dialog.element_handle())
                    visibility = browser.evaluate("el => window.getComputedStyle(el).visibility", first_dialog.element_handle())
                    print(f"Dialog styles - opacity: {opacity}, display: {display}, visibility: {visibility}")
            
            # Look for any form elements
            forms = browser.locator("form")
            print(f"Found {forms.count()} form(s)")
            
            # Look for input fields
            inputs = browser.locator("input[type='text'], input[type='email'], input:not([type])")
            print(f"Found {inputs.count()} text input(s)")
            
            # Look for the Additional Information section
            additional_info = browser.locator("text=Additional Information")
            if additional_info.count() > 0:
                print(f"Found 'Additional Information' section, visible: {additional_info.is_visible()}")
            else:
                print("No 'Additional Information' section found")
                
            # List all visible buttons in any modal/dialog
            visible_buttons = browser.locator("button:visible")
            print(f"\nVisible buttons on page ({visible_buttons.count()}):")
            for i in range(min(10, visible_buttons.count())):  # List first 10
                btn = visible_buttons.nth(i)
                text = btn.inner_text().strip()
                if text:
                    print(f"  - '{text}'")
                    
        else:
            print("Create button not visible")
            
    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_debug_incident_creation_ui")
        browser.screenshot(path="debug_error.png")
        raise e
    finally:
        # Always close any open modals
        try:
            browser.keyboard.press("Escape")
        except:
            pass


# Run with: pytest -s tests/e2e_tests/test_incident_form_schema_debug.py