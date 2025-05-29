from playwright.sync_api import Page

from tests.e2e_tests.utils import save_failure_artifacts


def test_start_with_keep_db(auth_page: Page, setup_page_logging, failure_artifacts):
    # Navigate to signin page
    auth_page.goto("http://localhost:3001/signin")
    # Wait for the page to load
    auth_page.wait_for_selector("text=Sign in")
    # Fill in credentials
    auth_page.get_by_placeholder("Enter your username").fill("keep")
    auth_page.get_by_placeholder("Enter your password").fill("keep")
    # Click sign in and wait for navigation
    auth_page.get_by_role("button", name="Sign in").click()
    try:
        auth_page.wait_for_url("http://localhost:3001/incidents", timeout=10000)
    except Exception:
        save_failure_artifacts(auth_page)
        raise
