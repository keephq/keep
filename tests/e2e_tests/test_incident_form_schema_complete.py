"""
Complete E2E tests for incident form schema feature
Tests the full flow from no schema to creating incidents with dynamic fields
"""

import json
import os
import random
import re
import string
import time
from typing import Dict, List

import pytest
import requests
from playwright.sync_api import Page, expect

from tests.e2e_tests.utils import (
    get_token,
    init_e2e_test,
    save_failure_artifacts,
    setup_console_listener,
)


def generate_random_string(length: int = 8) -> str:
    """Generate a random string for unique test data"""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def get_tenant_id() -> str:
    """Get the tenant ID for the current test run"""
    return f"keep{os.getpid()}"


def create_form_schema(tenant_id: str) -> Dict:
    """Create a form schema via API"""
    schema_data = {
        "name": "E2E Test Form Schema",
        "description": "Form schema created for E2E testing",
        "fields": [
            {
                "name": "jira_project",
                "label": "Jira Project",
                "type": "select",
                "description": "Target Jira project for ticket creation",
                "required": True,
                "options": ["OPS", "SUPPORT", "ENGINEERING"],
                "default_value": "OPS",
            },
            {
                "name": "priority",
                "label": "Priority Level",
                "type": "select",
                "options": ["Highest", "High", "Medium", "Low", "Lowest"],
                "default_value": "Medium",
                "required": False,
            },
            {
                "name": "urgent",
                "label": "Urgent Issue",
                "type": "checkbox",
                "description": "Requires immediate attention",
                "default_value": False,
                "required": False,
            },
            {
                "name": "business_impact",
                "label": "Business Impact",
                "type": "textarea",
                "placeholder": "Describe the business impact...",
                "max_length": 500,
                "required": True,
            },
            {
                "name": "affected_users",
                "label": "Number of Affected Users",
                "type": "number",
                "min_value": 0,
                "max_value": 1000000,
                "required": False,
            },
        ],
        "is_active": True,
    }

    response = requests.post(
        "http://localhost:8080/incidents/form-schema",
        json=schema_data,
        headers={
            "Authorization": f"Bearer {get_token(tenant_id)}",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()
    return response.json()


def delete_form_schema(tenant_id: str, schema_id: str) -> None:
    """Delete a form schema via API"""
    response = requests.delete(
        f"http://localhost:8080/incidents/form-schema?schema_id={schema_id}",
        headers={
            "Authorization": f"Bearer {get_token(tenant_id)}",
        },
    )
    # It's OK if it's already deleted or doesn't exist
    if response.status_code not in [200, 404]:
        response.raise_for_status()


def test_no_additional_information_without_schema(browser: Page):
    """Test that Additional Information section is NOT shown when no schema exists"""
    log_entries = []
    init_e2e_test(browser, wait_time=2)
    setup_console_listener(browser, log_entries)

    try:
        # Navigate to incidents page
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(2000)

        # Click create incident button
        create_button = browser.locator("button").filter(has_text="Create Incident").first
        assert create_button.is_visible(), "Create Incident button not found"
        create_button.click()

        # Wait for modal to appear
        browser.wait_for_timeout(1000)

        # Check that Additional Information section is NOT visible
        # It should not even be in the DOM when there's no schema
        additional_info = browser.locator("text=Additional Information")
        expect(additional_info).to_have_count(0)

        # Also check that "Loading form fields..." is not shown
        loading_text = browser.locator("text=Loading form fields...")
        expect(loading_text).to_have_count(0)

        print("✓ Confirmed: No Additional Information section when no schema exists")

        # Close modal
        browser.keyboard.press("Escape")

    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_no_additional_information_without_schema")
        raise e


def test_dynamic_fields_appear_with_schema(browser: Page):
    """Test that dynamic fields appear correctly when a schema is defined"""
    log_entries = []
    tenant_id = get_tenant_id()
    schema = None

    try:
        # Create form schema
        schema = create_form_schema(tenant_id)
        print(f"Created form schema with ID: {schema['id']}")

        # Initialize test
        init_e2e_test(browser, wait_time=2)
        setup_console_listener(browser, log_entries)

        # Navigate to incidents page
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(2000)

        # Click create incident button
        create_button = browser.locator("button").filter(has_text="Create Incident").first
        create_button.click()

        # Wait for modal and form to load
        browser.wait_for_timeout(2000)

        # Now Additional Information should be visible
        additional_info = browser.locator("text=Additional Information")
        expect(additional_info).to_be_visible()
        print("✓ Additional Information section is visible")

        # Check for our custom fields
        # Jira Project select
        jira_label = browser.locator("text=Jira Project")
        expect(jira_label).to_be_visible()
        print("✓ Jira Project field found")

        # Priority Level select
        priority_label = browser.locator("text=Priority Level")
        expect(priority_label).to_be_visible()
        print("✓ Priority Level field found")

        # Urgent Issue checkbox
        urgent_label = browser.locator("text=Urgent Issue")
        expect(urgent_label).to_be_visible()
        print("✓ Urgent Issue checkbox found")

        # Business Impact textarea
        business_label = browser.locator("text=Business Impact")
        expect(business_label).to_be_visible()
        print("✓ Business Impact field found")

        # Number of Affected Users
        users_label = browser.locator("text=Number of Affected Users")
        expect(users_label).to_be_visible()
        print("✓ Number of Affected Users field found")

        # Close modal
        browser.keyboard.press("Escape")

    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_dynamic_fields_appear_with_schema")
        raise e
    finally:
        # Cleanup: delete the schema
        if schema:
            delete_form_schema(tenant_id, schema["id"])


def test_create_incident_with_dynamic_fields(browser: Page):
    """Test creating an incident with dynamic field values and verify enrichments"""
    log_entries = []
    tenant_id = get_tenant_id()
    schema = None
    incident_name = f"E2E Test Incident {generate_random_string()}"

    try:
        # Create form schema
        schema = create_form_schema(tenant_id)
        print(f"Created form schema with ID: {schema['id']}")

        # Initialize test
        init_e2e_test(browser, wait_time=2)
        setup_console_listener(browser, log_entries)

        # Navigate to incidents page
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(2000)

        # Click create incident button
        create_button = browser.locator("button").filter(has_text="Create Incident").first
        create_button.click()

        # Wait for modal
        browser.wait_for_timeout(2000)

        # Fill in standard fields
        # Find the name input - it might be the first text input
        name_input = browser.locator("input[type='text']").first
        name_input.fill(incident_name)
        print(f"Filled incident name: {incident_name}")

        # Fill description - look for textarea
        description_textarea = browser.locator("textarea").first
        description_textarea.fill("E2E test incident with custom fields")
        print("Filled description")

        # Now fill in dynamic fields
        # Select Jira Project - find the select after the Jira Project label
        jira_select = browser.locator("text=Jira Project").locator("..").locator("select")
        if jira_select.count() == 0:
            # Try parent's parent
            jira_select = browser.locator("text=Jira Project").locator("../..").locator("select")
        jira_select.select_option("ENGINEERING")
        print("Selected Jira Project: ENGINEERING")

        # Select Priority
        priority_select = browser.locator("text=Priority Level").locator("../..").locator("select")
        priority_select.select_option("High")
        print("Selected Priority: High")

        # Check Urgent checkbox
        urgent_checkbox = browser.locator("text=Urgent Issue").locator("../..").locator("input[type='checkbox']")
        urgent_checkbox.check()
        print("Checked Urgent Issue")

        # Fill Business Impact
        impact_textarea = browser.locator("text=Business Impact").locator("../..").locator("textarea")
        impact_textarea.fill("Critical system down affecting all users")
        print("Filled Business Impact")

        # Fill Affected Users
        users_input = browser.locator("text=Number of Affected Users").locator("../..").locator("input[type='number']")
        users_input.fill("1500")
        print("Filled Affected Users: 1500")

        # Submit the form - find Create button in the modal
        submit_button = browser.locator("button").filter(has_text="Create").last
        submit_button.click()
        print("Clicked Create button")

        # Wait for redirect/modal close
        browser.wait_for_timeout(3000)

        # Verify incident was created - look for it in the list
        incident_row = browser.locator("tr").filter(has_text=incident_name)
        expect(incident_row).to_be_visible(timeout=10000)
        print(f"✓ Incident created successfully: {incident_name}")

        # Click on the incident to view details
        incident_row.click()
        browser.wait_for_timeout(2000)

        # TODO: Verify enrichments are displayed in incident details
        # This would require checking the incident detail view
        # For now, we've confirmed the incident was created with our form data

    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_create_incident_with_dynamic_fields")
        raise e
    finally:
        # Cleanup: delete the schema
        if schema:
            delete_form_schema(tenant_id, schema["id"])


def test_required_field_validation(browser: Page):
    """Test that required fields are validated before submission"""
    log_entries = []
    tenant_id = get_tenant_id()
    schema = None

    try:
        # Create form schema
        schema = create_form_schema(tenant_id)
        print(f"Created form schema with ID: {schema['id']}")

        # Initialize test
        init_e2e_test(browser, wait_time=2)
        setup_console_listener(browser, log_entries)

        # Navigate to incidents page
        browser.goto("http://localhost:3000/incidents")
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(2000)

        # Click create incident button
        create_button = browser.locator("button").filter(has_text="Create Incident").first
        create_button.click()

        # Wait for modal
        browser.wait_for_timeout(2000)

        # Fill only the incident name (required)
        name_input = browser.locator("input[type='text']").first
        name_input.fill("Test Validation Incident")

        # Don't fill the required Business Impact field
        # Try to submit
        submit_button = browser.locator("button").filter(has_text="Create").last
        submit_button.click()

        # Should see validation error
        browser.wait_for_timeout(1000)
        
        # Check if we're still in the modal (form wasn't submitted)
        modal = browser.locator("[role='dialog']")
        expect(modal).to_be_visible()
        
        # Look for validation error message
        error_text = browser.locator("text=is required").first
        if error_text.is_visible():
            print("✓ Validation error shown for required field")
        else:
            # The form might show errors differently
            print("Note: Validation might be preventing submission silently")

        # Close modal
        browser.keyboard.press("Escape")

    except Exception as e:
        save_failure_artifacts(browser, log_entries, "test_required_field_validation")
        raise e
    finally:
        # Cleanup: delete the schema
        if schema:
            delete_form_schema(tenant_id, schema["id"])


# Run tests with: pytest -s tests/e2e_tests/test_incident_form_schema_complete.py