import pytest
from playwright.sync_api import Page
from tests.e2e_tests.incidents_alerts_tests.incidents_alerts_setup import (
    create_fake_alert,
    upload_alert,
    upload_incident,
)
from tests.e2e_tests.utils import init_e2e_test, save_failure_artifacts

KEEP_UI_URL = "http://localhost:3000"


@pytest.fixture
def xss_incident():
    incident = {
        "user_generated_name": '<script>alert("XSS")</script>',
        "user_summary": '<script>alert("XSS")</script>',
    }
    return upload_incident(incident)


def test_xss_protection_in_incident_list(
    browser: Page, xss_incident, setup_page_logging, failure_artifacts
):
    xss_dialog_appeared = False

    def handle_dialog(dialog):
        nonlocal xss_dialog_appeared
        if dialog.message == "XSS":
            xss_dialog_appeared = True
        dialog.dismiss()

    try:
        browser.on("dialog", handle_dialog)

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

    finally:
        browser.remove_listener("dialog", handle_dialog)


@pytest.fixture
def xss_alert():
    alert = create_fake_alert(0, "datadog")
    if not alert:
        raise Exception("Failed to create fake alert")
    alert["name"] = "XSS Alert"
    alert["description"] = '<script>alert("XSS")</script>'
    alert["description_format"] = "html"
    upload_alert("", alert)
    return alert


def test_xss_protection_in_alert_description(browser: Page, xss_alert):
    init_e2e_test(browser, next_url="/alerts/feed")
    browser.wait_for_timeout(1000)
    cel_input_locator = browser.locator(".alerts-cel-input")
    cel_input_locator.click()
    cel_input_locator.type(f'name == "{xss_alert["name"]}"')
    browser.keyboard.press("Enter")
    browser.wait_for_timeout(1000)
    browser.locator(
        "table[data-testid='alerts-table'] tbody tr",
        has_text=xss_alert["name"],
    ).first.click()
    description_locator = browser.get_by_role("heading", name="Description").locator(
        ".."
    )
    html_content = description_locator.inner_html()
    assert "<script>" not in html_content, "Unescaped script tag found in HTML"


@pytest.fixture
def legit_html_incident():
    incident = {
        "user_generated_name": "Incident with rich html description",
        # newlines are important as it changes how markdown is rendered
        "user_summary": '\n        <h2>Test Failure: <code>test_csb_upload_send_two_times_same_sequence_number</code></h2>\n        <h3><a href="https://google.com">Google</a></h3>\n        ',
    }
    return upload_incident(incident)


def test_legit_html_content(browser: Page, legit_html_incident):
    try:
        init_e2e_test(browser, next_url="/incidents")
        browser.wait_for_timeout(1000)
        incident_row = browser.locator(
            "table[data-testid='incidents-table'] tbody tr",
            has_text=legit_html_incident["user_generated_name"],
        ).first
        html_content = incident_row.inner_html()
        assert "<h2>" in html_content, "H2 tag not found in HTML"
        assert "<code>" in html_content, "Code tag not found in HTML"
        assert (
            '<a href="https://google.com">' in html_content
        ), "Link tag not found in HTML"
    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise


@pytest.fixture
def alert_legit_html_content():
    alert = create_fake_alert(0, "datadog")
    if not alert:
        raise Exception("Failed to create fake alert")
    # newlines are important as it changes how markdown is rendered
    alert["name"] = "Alert with legit html content"
    alert["description"] = (
        '\n        <h2>Test Failure: <code>test_csb_upload_send_two_times_same_sequence_number</code></h2>\n        <h3><a href="https://google.com">Google</a></h3>\n        '
    )
    alert["description_format"] = "html"
    upload_alert("", alert)
    return alert


def test_legit_html_content_in_alert_description(
    browser: Page, alert_legit_html_content
):
    init_e2e_test(browser, next_url="/alerts/feed")
    browser.wait_for_timeout(1000)
    cel_input_locator = browser.locator(".alerts-cel-input")
    cel_input_locator.click()
    cel_input_locator.type(f'name == "{alert_legit_html_content["name"]}"')
    browser.keyboard.press("Enter")
    browser.wait_for_timeout(1000)
    browser.locator(
        "table[data-testid='alerts-table'] tbody tr",
        has_text=alert_legit_html_content["name"],
    ).first.click()
    description_locator = browser.get_by_role("heading", name="Description").locator(
        ".."
    )
    html_content = description_locator.inner_html()
    assert "<h2>" in html_content, "H2 tag not found in HTML"
    assert "<code>" in html_content, "Code tag not found in HTML"
    assert '<a href="https://google.com">' in html_content, "Link tag not found in HTML"
    assert "<h3>" in html_content, "H3 tag not found in HTML"
