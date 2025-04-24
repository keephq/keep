from playwright.sync_api import Page

from tests.e2e_tests.utils import save_failure_artifacts


def test_start_with_keep_db(browser: Page, setup_page_logging, failure_artifacts):
    # Navigate to signin page
    browser.goto("http://localhost:3001/signin")
    # Wait for the page to load
    browser.wait_for_selector("text=Sign in")
    # Fill in credentials
    browser.get_by_placeholder("Enter your username").fill("keep")
    browser.get_by_placeholder("Enter your password").fill("keep")
    # Click sign in and wait for navigation
    browser.get_by_role("button", name="Sign in").click()
    try:
        browser.wait_for_url("http://localhost:3001/incidents", timeout=10000)
    except Exception:
        save_failure_artifacts(browser)
        raise
