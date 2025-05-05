import re
from playwright.sync_api import Page, expect
from tests.e2e_tests.test_end_to_end import init_e2e_test, setup_console_listener
from tests.e2e_tests.utils import save_failure_artifacts


KEEP_UI_URL = "http://localhost:3000"

def test_quill_mentions_in_comments(browser: Page, setup_page_logging, failure_artifacts):
    test_id = "test_quill_mentions"
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
        summary_div.locator("div").nth(3).fill("Test Incident Summary for quill mentions test")

        browser.get_by_role("button", name="Who is responsible").click()
        browser.get_by_role("option", name="keep").click()

        # Create a new incident
        browser.get_by_role("button", name="Create").click()

        browser.get_by_role("link", name=incident_title, exact=True).click()

        browser.get_by_role("tab", name="Activity").click()

        # Wait for the Quill editor to load
        browser.wait_for_selector(".ql-editor")
        
        # Type in the Quill editor
        browser.locator(".ql-editor").click()
        browser.locator(".ql-editor").fill("Test comment with ")
        
        # Type @ to trigger mentions
        browser.locator(".ql-editor").press("@")
        
        # Wait for the mention list to appear
        browser.wait_for_selector(".ql-mention-list-container")
        
        # Select the first user from the dropdown
        browser.locator(".ql-mention-list-item").first.click()
        
        # Add some more text
        browser.locator(".ql-editor").press(" and more text")
        
        # Submit the comment
        browser.get_by_role("button", name="Comment").click()
        
        # Verify the mention is visible in the comment
        browser.wait_for_selector(".mention")
        expect(browser.locator(".mention")).to_be_visible()

    except Exception as e:
        save_failure_artifacts(browser, log_entries=log_entries)
        raise e
