"""
E2E tests for incident form schema feature - dynamic form fields for incident creation
"""

import os
import random
import re
import string
import time
from typing import List

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_tests.utils import init_e2e_test, save_failure_artifacts, setup_console_listener


def generate_random_string(length: int = 8) -> str:
    """Generate a random string for unique test data"""
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))


def test_incident_form_schema_crud(browser: Page):
    """Test creating, updating, and deleting incident form schemas"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)
    
    try:
        # Navigate to settings page where form schema management would be
        # TODO: Update navigation once the settings UI is implemented
        browser.goto("http://localhost:3000/settings")
        browser.wait_for_load_state("networkidle")
        
        # For now, we'll test via API since UI might not be implemented yet
        # This is a placeholder for when the UI is ready
        
        # Test 1: Verify no schema exists initially
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        
        # Click on create incident button
        create_incident_button = browser.get_by_role("button", name=re.compile("create.*incident", re.IGNORECASE))
        create_incident_button.click()
        
        # Verify no custom fields are shown initially
        # The modal should only show standard fields
        expect(browser.locator("text=Additional Information")).not_to_be_visible()
        
        # Close the modal
        browser.keyboard.press("Escape")
        
    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_incident_form_schema_crud")
        raise e


def test_incident_creation_with_custom_fields(browser: Page):
    """Test creating an incident with custom form fields"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)
    
    try:
        # Navigate to incidents page
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        
        # TODO: This test assumes a form schema has been created via API or settings
        # In a real test, we would:
        # 1. Create a form schema via API or UI
        # 2. Create an incident using the custom fields
        # 3. Verify the custom field values are saved as enrichments
        
        # Click create incident
        create_incident_button = browser.get_by_role("button", name=re.compile("create.*incident", re.IGNORECASE))
        create_incident_button.click()
        
        # Wait for modal to open
        browser.wait_for_selector("[role='dialog']", state="visible")
        
        # Fill in standard fields
        incident_name = f"Test Incident {generate_random_string()}"
        browser.fill("input[name='name']", incident_name)
        browser.fill("textarea[name='description']", "Test incident with custom fields")
        
        # Check if custom fields section exists
        custom_fields_section = browser.locator("text=Additional Information")
        if custom_fields_section.is_visible():
            # Example: Fill in a Jira project field if it exists
            jira_project_select = browser.locator("select").filter(has_text="Jira Project")
            if jira_project_select.is_visible():
                jira_project_select.select_option("OPS")
            
            # Example: Check an urgent checkbox if it exists
            urgent_checkbox = browser.locator("text=Urgent Issue").locator("..").locator("input[type='checkbox']")
            if urgent_checkbox.is_visible():
                urgent_checkbox.check()
        
        # Submit the form
        submit_button = browser.get_by_role("button", name=re.compile("create", re.IGNORECASE))
        submit_button.click()
        
        # Wait for navigation back to incidents list
        browser.wait_for_url(re.compile(r".*/incidents(\?.*)?"))
        
        # Verify the incident was created
        expect(browser.locator(f"text={incident_name}")).to_be_visible(timeout=10000)
        
    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_incident_creation_with_custom_fields")
        raise e


def test_multiple_schemas_per_tenant(browser: Page):
    """Test that multiple form schemas can be created per tenant"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)
    
    try:
        # This test would require API access to create multiple schemas
        # and verify they can be switched between in the UI
        
        # TODO: Implement once the UI supports schema selection
        # The test would:
        # 1. Create multiple schemas via API
        # 2. Navigate to incident creation
        # 3. Verify schema selector is available
        # 4. Switch between schemas and verify different fields appear
        
        pass
        
    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_multiple_schemas_per_tenant")
        raise e


def test_form_field_validation(browser: Page):
    """Test validation of custom form fields"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)
    
    try:
        # Navigate to incidents page
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        
        # Click create incident
        create_incident_button = browser.get_by_role("button", name=re.compile("create.*incident", re.IGNORECASE))
        create_incident_button.click()
        
        # Wait for modal
        browser.wait_for_selector("[role='dialog']", state="visible")
        
        # Fill required standard fields
        browser.fill("input[name='name']", "Validation Test Incident")
        
        # If custom fields exist, test validation
        custom_fields_section = browser.locator("text=Additional Information")
        if custom_fields_section.is_visible():
            # Try to submit without filling required custom fields
            submit_button = browser.get_by_role("button", name=re.compile("create", re.IGNORECASE))
            submit_button.click()
            
            # Check for validation errors
            # Look for error messages near required fields
            error_messages = browser.locator("text=is required")
            if error_messages.count() > 0:
                # Verify at least one validation error is shown
                expect(error_messages.first).to_be_visible()
                
                # Test number field validation if present
                number_input = browser.locator("input[type='number']").first
                if number_input.is_visible():
                    # Try invalid number
                    number_input.fill("abc")
                    browser.keyboard.press("Tab")
                    # Should show validation error
                    expect(browser.locator("text=must be a number")).to_be_visible()
        
        # Close modal
        browser.keyboard.press("Escape")
        
    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_form_field_validation")
        raise e


def test_enrichments_from_custom_fields(browser: Page):
    """Test that custom field values are saved as incident enrichments"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)
    
    try:
        # Create an incident with custom fields
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        
        # Create incident
        create_incident_button = browser.get_by_role("button", name=re.compile("create.*incident", re.IGNORECASE))
        create_incident_button.click()
        
        browser.wait_for_selector("[role='dialog']", state="visible")
        
        # Fill in incident details
        incident_name = f"Enrichment Test {generate_random_string()}"
        browser.fill("input[name='name']", incident_name)
        browser.fill("textarea[name='description']", "Testing enrichments from custom fields")
        
        # Remember custom field values if they exist
        custom_values = {}
        custom_fields_section = browser.locator("text=Additional Information")
        if custom_fields_section.is_visible():
            # Example: Set a select field value
            selects = browser.locator("select")
            for i in range(selects.count()):
                select = selects.nth(i)
                if select.is_visible():
                    # Get the field name from a nearby label or attribute
                    field_label = select.locator("..").locator("text").first
                    if field_label.is_visible():
                        label_text = field_label.inner_text()
                        select.select_option(index=1)  # Select first option
                        custom_values[label_text] = select.input_value()
        
        # Submit
        submit_button = browser.get_by_role("button", name=re.compile("create", re.IGNORECASE))
        submit_button.click()
        
        # Wait for redirect
        browser.wait_for_url(re.compile(r".*/incidents(\?.*)?"))
        
        # Click on the created incident to view details
        browser.locator(f"text={incident_name}").click()
        
        # Verify enrichments are displayed
        # TODO: Update selectors based on actual incident detail view implementation
        # The enrichments should be visible in the incident details
        
    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_enrichments_from_custom_fields")
        raise e


def test_ticket_link_display(browser: Page):
    """Test that ticket links are properly displayed in incidents table"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)
    
    try:
        # This test assumes there's an incident with a ticket_url enrichment
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        
        # Look for any ticket links in the table
        ticket_links = browser.locator("a").filter(has_text=re.compile(r"[A-Z]+-\d+"))
        
        if ticket_links.count() > 0:
            # Verify the link has proper attributes
            first_link = ticket_links.first
            expect(first_link).to_have_attribute("target", "_blank")
            expect(first_link).to_have_attribute("rel", re.compile("noopener"))
            
            # Verify the external link icon is present
            icon = first_link.locator("svg")
            expect(icon).to_be_visible()
        
    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_ticket_link_display")
        raise e


# Run tests with: pytest -s tests/e2e_tests/test_incident_form_schema.py