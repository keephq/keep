import re
from playwright.sync_api import Page, expect
from tests.e2e_tests.test_end_to_end import init_e2e_test, setup_console_listener
from tests.e2e_tests.utils import save_failure_artifacts


KEEP_UI_URL = "http://localhost:3000"

def test_mentions_in_incident_comments(browser: Page, setup_page_logging, failure_artifacts):
    test_id = "test_mentions_in_comments"
    log_entries = []
    setup_console_listener(browser, log_entries)

    # Initialize test and go to incidents page
    init_e2e_test(browser, next_url="/incidents")
    browser.wait_for_selector("[data-testid='incidents-table']")

    try:
        browser.get_by_role("button", name="Create Incident").click()

        incident_title = f"Test Incident {test_id}"
        browser.get_by_test_id("base-input").click()
        browser.get_by_test_id("base-input").fill(incident_title)

        summary_div = browser.locator("div").filter(has_text=re.compile(r"^Summary$"))
        summary_div.get_by_role("paragraph").nth(1).click()
        summary_div.locator("div").nth(3).fill("Test Incident Summary for mentions test")

        browser.get_by_role("button", name="Who is responsible").click()
        browser.get_by_role("option", name="keep").click()

        # Create a new incident
        browser.get_by_role("button", name="Create").click()

        browser.get_by_role("link", name=incident_title, exact=True).click()

        browser.get_by_role("tab", name="Activity").click()

        browser.get_by_test_id("base-input").click()
        browser.get_by_test_id("base-input").fill("Test comment @keep")

        browser.wait_for_selector("text=keep", timeout=5000)
        browser.get_by_text("keep").nth(2).click()

        # Test keyboard navigation
        browser.get_by_test_id("base-input").click()
        browser.get_by_test_id("base-input").fill(browser.get_by_test_id("base-input").input_value() + " and also @")
        browser.wait_for_selector("text=keep", timeout=5000)

        # Use keyboard to navigate and select
        browser.keyboard.press("ArrowDown")
        browser.keyboard.press("ArrowDown")
        browser.keyboard.press("Enter")

        browser.get_by_role("button", name="Comment").click()

        # Verify the mentions are visible
        expect(browser.get_by_text("@keep")).to_be_visible()

        # Check if notification appears (this is a mock, so it should appear after 5 seconds)
        browser.wait_for_timeout(6000)  # Wait for mock notification to appear
        notification_bell = browser.locator("svg[viewBox='0 0 24 24']").nth(0)
        notification_bell.click()

        # Verify notification content
        expect(browser.get_by_text("You were mentioned in a comment")).to_be_visible()

    except Exception as e:
        save_failure_artifacts(browser, log_entries=log_entries)
        raise e
