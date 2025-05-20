import pytest
from playwright.sync_api import Page
from tests.e2e_tests.incidents_alerts_tests.incidents_alerts_setup import (
    upload_incident,
)
from tests.e2e_tests.utils import init_e2e_test, save_failure_artifacts

KEEP_UI_URL = "http://localhost:3000"


@pytest.fixture(scope="module")
def xss_incident():
    incident = {
        "user_generated_name": '<script>alert("XSS")</script>',
        "user_summary": '<script>alert("XSS")</script>',
    }
    return upload_incident(incident)


def test_xss_protection_in_incident_list(browser: Page, xss_incident):
    xss_dialog_appeared = False

    def handle_dialog(dialog):
        nonlocal xss_dialog_appeared
        if dialog.message == "XSS":
            xss_dialog_appeared = True
        dialog.dismiss()

    try:
        browser.context.on("dialog", handle_dialog)

        # Initialize the test
        init_e2e_test(browser, next_url="/incidents")

        browser.wait_for_timeout(1000)

        assert not xss_dialog_appeared, "XSS attack succeeded - alert dialog appeared"

        # Verify that the XSS payload is properly escaped in the table
        incident_row = browser.locator(
            "table[data-testid='incidents-table'] tbody tr",
            has_text=xss_incident["user_generated_name"],
        ).first

        # Additional check - verify the content is properly escaped in HTML
        html_content = incident_row.inner_html()
        assert "<script>" not in html_content, "Unescaped script tag found in HTML"

    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise
