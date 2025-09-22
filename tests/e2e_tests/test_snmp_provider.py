import re
from datetime import datetime

from playwright.sync_api import Page, expect

from tests.e2e_tests.utils import (
    assert_connected_provider_count,
    assert_scope_text_count,
    delete_provider,
    init_e2e_test,
    open_connected_provider,
    save_failure_artifacts,
    trigger_alert,
)


KEEP_UI_URL = "http://localhost:3000"
DEFAULT_SNMP_PORT = 1162  # Standard SNMP trap port


def open_snmp_card(browser):
    """Open the SNMP provider card in the UI."""
    browser.get_by_placeholder("Filter providers...").click()
    browser.get_by_placeholder("Filter providers...").clear()
    browser.get_by_placeholder("Filter providers...").fill("SNMP")
    browser.get_by_placeholder("Filter providers...").press("Enter")
    browser.get_by_text("Available Providers").hover()
    snmp_tile = browser.locator(
        "button:has-text('SNMP'):not(:has-text('Connected')):not(:has-text('Linked'))"
    )
    snmp_tile.first.hover()
    snmp_tile.first.click()


def test_snmp_provider(browser: Page, setup_page_logging, failure_artifacts):
    """End-to-end test for the SNMP Provider."""
    try:
        provider_name = "playwright_test_snmp_" + datetime.now().strftime("%Y%m%d%H%M%S")

        # Initialize the test and navigate to the providers page
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                init_e2e_test(
                    browser,
                    next_url="/signin?callbackUrl=http%3A%2F%2Flocalhost%3A3000%2Fproviders",
                )
                # Give the page a moment to process redirects
                browser.wait_for_timeout(500)
                # Wait for navigation to complete
                browser.wait_for_load_state("networkidle")

                base_url = "http://localhost:3000/providers"
                url_pattern = re.compile(f"{re.escape(base_url)}(\\?.*)?$")
                browser.wait_for_url(url_pattern)
                print(f"Providers page loaded successfully. [try: {attempt + 1}]")
                break
            except Exception as e:
                if attempt < max_attempts - 1:
                    print("Failed to load providers page. Retrying...")
                    continue
                else:
                    raise e

        browser.get_by_role("link", name="Providers").hover()
        browser.get_by_role("link", name="Providers").click()
        browser.wait_for_timeout(5000)
        
        severity_mapping = '{"1.3.6.1.6.3.1.1.5.1": "INFO", "1.3.6.1.6.3.1.1.5.2": "WARNING", "1.3.6.1.6.3.1.1.5.3": "ERROR", "1.3.6.1.6.3.1.1.5.4": "WARNING", "1.3.6.1.6.3.1.1.5.5": "CRITICAL"}'

        # Open the SNMP provider configuration
        open_snmp_card(browser)
        
        # Wait for UI to stabilize
        browser.wait_for_timeout(3000)
        
        # Fill in the provider configuration
        browser.get_by_placeholder("Enter provider name").fill(provider_name)
        browser.get_by_placeholder("Enter listen_address").fill("0.0.0.0")
        browser.get_by_placeholder("Enter port").fill(str(DEFAULT_SNMP_PORT))
        browser.get_by_placeholder("Enter community").fill("public")
        browser.get_by_placeholder("Enter severity_mapping").fill(severity_mapping)
        
        # Wait for UI to stabilize and remove any validation overlays
        browser.wait_for_timeout(2000)
        
        # Remove any overlays that appeared during form filling
        browser.evaluate(
            """() => {
            const overlays = document.querySelectorAll('div[data-enter][data-closed][aria-hidden="true"], div[aria-hidden="true"], nextjs-portal');
            overlays.forEach(overlay => overlay.remove());
        }"""
        )
        browser.wait_for_timeout(1000)
        
        # Connect the provider
        browser.get_by_role("button", name="Connect", exact=True).click()
        
        print("Connected provider")
        browser.reload()
        
        # Wait for the provider to be connected
        expect(
            browser.locator(f"button:has-text('SNMP'):has-text('Connected'):has-text('{provider_name}')")
        ).to_be_visible(timeout=10000)
        
        # Wait for page to stabilize before proceeding
        browser.wait_for_load_state("networkidle")
        
        # Open the connected provider to check scope validation
        open_connected_provider(
            browser=browser,
            provider_type="SNMP",
            provider_name=provider_name,
        )
        
        # Check that the receive_traps scope is valid
        assert_scope_text_count(browser=browser, contains_text="Valid", count=1)
        
        # Close the provider details
        browser.get_by_role("button", name="Cancel", exact=True).click()
        
        print("Simulating SNMP trap reception...")
        
        # Use the trigger_alert utility function to simulate an SNMP alert
        # This follows the same pattern as other e2e tests
        trigger_alert("snmp")
        
        # Wait for the alert to be processed
        browser.wait_for_timeout(3000)
        
        # Navigate to the Feed page to check for alerts
        browser.get_by_role("link", name="Feed").hover()
        browser.get_by_role("link", name="Feed").click()
        
        # Check for the SNMP trap alert
        max_attempts = 5
        for attempt in range(max_attempts):
            print(f"Attempt {attempt + 1} to load alerts...")
            browser.get_by_role("link", name="Feed").click()
            
            try:
                # Wait for SNMP trap alert to appear
                browser.wait_for_selector("text=SNMP Trap", timeout=5000)
                print("SNMP Trap alert loaded successfully.")
                break
            except Exception:
                if attempt < max_attempts - 1:
                    print("SNMP alert not loaded yet. Retrying...")
                    browser.reload()
                else:
                    print("Failed to load SNMP alert after maximum attempts.")
                    raise Exception("Failed to load SNMP alert after maximum attempts.")
        
        # Clean up - delete the provider
        browser.get_by_role("link", name="Providers").hover()
        browser.get_by_role("link", name="Providers").click()
        
        delete_provider(
            browser=browser,
            provider_type="SNMP",
            provider_name=provider_name,
        )
        
        # Assert provider was deleted
        assert_connected_provider_count(
            browser=browser,
            provider_type="SNMP",
            provider_name=provider_name,
            provider_count=0,
        )
        
    except Exception as e:
        print(f"Test failed with error: {str(e)}")
        # Save artifacts for debugging
        save_failure_artifacts(browser)
        raise 