import re
import pytest
from playwright.sync_api import Page, expect
from tests.e2e_tests.utils import init_e2e_test
from tests.e2e_tests.test_end_to_end import setup_console_listener

KEEP_UI_URL = "http://localhost:3000"


def init_test(browser: Page, max_retries=3):
    for i in range(max_retries):
        try:
            init_e2e_test(browser, next_url="/incidents")
            base_url = f"{KEEP_UI_URL}/incidents"
            # we don't care about query params
            # Give the page a moment to process redirects
            browser.wait_for_timeout(500)
            # Wait for navigation to complete to either signin or providers page
            # (since we might get redirected automatically)
            browser.wait_for_load_state("networkidle")
            browser.wait_for_url(lambda url: url.startswith(base_url), timeout=10000)
            print("Page loaded successfully. [try: %d]" % (i + 1))
            break
        except Exception as e:
            if i < max_retries - 1:
                print("Failed to load incidents page. Retrying... - ", e)
                continue
            else:
                raise e


@pytest.fixture
def setup_test_data():
    """Setup test data for the mentions test"""
    # This test doesn't require pre-existing data
    # but follows the pattern of other tests for consistency
    return {}


def test_mentions_in_incident_comments(browser: Page, setup_test_data, setup_page_logging, failure_artifacts):
    """Test that mentions in incident comments work correctly"""
    log_entries = []
    setup_console_listener(browser, log_entries)
    
    try:
        init_test(browser)
        browser.wait_for_load_state("networkidle")
        page = browser
        
        page.get_by_role("button", name="Create Incident").click()
        page.get_by_placeholder("Incident Name").click()
        page.get_by_placeholder("Incident Name").fill("Test Incident")
        page.locator("div").filter(has_text=re.compile(r"^Summary$")).get_by_role("paragraph").nth(1).click()
        page.locator("div").filter(has_text=re.compile(r"^Summary$")).locator("div").nth(3).fill("Test summary")
        page.get_by_role("button", name="Create", exact=True).click()
        
        page.wait_for_load_state("networkidle")
        page.get_by_role("link", name="Test Incident").click()
        
        page.wait_for_load_state("networkidle")
        page.get_by_role("tab", name="Activity").click()
        
        page.wait_for_selector("[data-testid='base-input']", timeout=10000)
        page.get_by_test_id("base-input").click()
        page.get_by_test_id("base-input").fill("@")
        page.wait_for_selector("text=John Smith", timeout=10000)
        page.get_by_text("John Smith").click()
        page.get_by_role("button", name="Comment").click()
        
        expect(page.get_by_text("@John Smith")).to_be_visible()

        
    except Exception as e:
        save_failure_artifacts(browser, log_entries=log_entries, failure_name=failure_artifacts)
        raise e