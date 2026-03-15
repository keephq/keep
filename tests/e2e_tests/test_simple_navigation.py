
import re
from playwright.sync_api import Page, expect

from tests.e2e_tests.utils import (
    init_e2e_test,
    save_failure_artifacts,
    setup_console_listener,
)


def test_simple_navigation(browser: Page, setup_page_logging, failure_artifacts):
    """
    Test to check simple navigation.
    """
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/providers")
        base_url = "http://localhost:3000/providers"
        url_pattern = re.compile(f"{re.escape(base_url)}(\\?.*)?$")
        browser.wait_for_url(url_pattern)
        expect(browser).to_have_title("Keep")
        expect(browser.get_by_text("Providers")).to_be_visible()
        browser.get_by_test_id("menu-alerts-feed-link").click()
        base_url = "http://localhost:3000/alerts"
        url_pattern = re.compile(f"{re.escape(base_url)}(\\?.*)?$")
        browser.wait_for_url(url_pattern)
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise
