"""
E2E test for backend column configuration persistence
Tests that column configurations are properly saved and restored from backend
"""

import pytest
import time
from playwright.sync_api import Page, expect

from tests.e2e.utils import (
    create_preset,
    delete_preset,
    wait_for_alert_table_to_load,
)


@pytest.fixture(scope="function")
def test_preset(authenticated_page: Page):
    """Create a test preset and clean it up after test"""
    preset_name = f"test_column_config_{int(time.time())}"
    
    # Create preset
    preset_data = create_preset(authenticated_page, preset_name)
    
    yield preset_data
    
    # Cleanup
    try:
        delete_preset(authenticated_page, preset_data["id"])
    except Exception as e:
        print(f"Failed to delete preset: {e}")


def test_backend_column_configuration_persistence(authenticated_page: Page, test_preset):
    """
    Test that column configurations are persisted in backend and restored on page reload
    """
    page = authenticated_page
    preset_id = test_preset["id"]
    
    # Navigate to the preset
    page.goto(f"/incidents?activePresetId={preset_id}")
    wait_for_alert_table_to_load(page)
    
    # Open column selection menu
    column_selection_button = page.locator('button[aria-label="Column Selection"]')
    column_selection_button.click()
    
    # Wait for column menu to be visible
    column_menu = page.locator('[role="menu"]').filter(has_text="Column Selection")
    expect(column_menu).to_be_visible()
    
    # Hide a specific column (e.g., "severity")
    severity_checkbox = column_menu.locator('input[type="checkbox"][value="severity"]')
    expect(severity_checkbox).to_be_checked()
    severity_checkbox.click()
    expect(severity_checkbox).not_to_be_checked()
    
    # Click outside to close menu
    page.locator("body").click(position={"x": 0, "y": 0})
    
    # Wait for the column to be hidden
    page.wait_for_timeout(1000)
    
    # Verify column is hidden
    severity_header = page.locator('th:has-text("Severity")')
    expect(severity_header).not_to_be_visible()
    
    # Reload the page
    page.reload()
    wait_for_alert_table_to_load(page)
    
    # Verify column is still hidden after reload
    severity_header = page.locator('th:has-text("Severity")')
    expect(severity_header).not_to_be_visible()
    
    # Re-open column selection and verify checkbox state
    column_selection_button.click()
    column_menu = page.locator('[role="menu"]').filter(has_text="Column Selection")
    expect(column_menu).to_be_visible()
    
    severity_checkbox = column_menu.locator('input[type="checkbox"][value="severity"]')
    expect(severity_checkbox).not_to_be_checked()
    
    # Re-enable the column for cleanup
    severity_checkbox.click()
    expect(severity_checkbox).to_be_checked()
    
    print("✅ Column configuration persistence test passed")


def test_column_order_persistence(authenticated_page: Page, test_preset):
    """
    Test that column order changes are persisted in backend
    """
    page = authenticated_page
    preset_id = test_preset["id"]
    
    # Navigate to the preset
    page.goto(f"/incidents?activePresetId={preset_id}")
    wait_for_alert_table_to_load(page)
    
    # Get initial column order
    headers = page.locator("thead th").all_text_contents()
    initial_order = [h for h in headers if h]  # Filter empty strings
    
    # TODO: Implement drag and drop to reorder columns
    # This would require implementing the drag and drop functionality
    # in the UI first
    
    print("✅ Column order persistence test placeholder")


def test_column_rename_persistence(authenticated_page: Page, test_preset):
    """
    Test that column rename configurations are persisted in backend
    """
    page = authenticated_page
    preset_id = test_preset["id"]
    
    # Navigate to the preset
    page.goto(f"/incidents?activePresetId={preset_id}")
    wait_for_alert_table_to_load(page)
    
    # TODO: Implement column rename functionality test
    # This would require implementing the rename functionality
    # in the UI first
    
    print("✅ Column rename persistence test placeholder")