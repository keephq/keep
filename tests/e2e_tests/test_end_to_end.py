# This file contains the end-to-end tests for Keep.

# There are two mode of operations:
# 1. Running the tests locally
# 2. Running the tests in GitHub Actions

# Running the tests in GitHub Actions:
# - Look at the test-pr-e2e.yml file in the .github/workflows directory.

# Running the tests locally:
# 1. Spin up the environment using docker-compose.
#   for mysql: docker compose --project-directory . -f tests/e2e_tests/docker-compose-e2e-mysql.yml up -d
#   for postgres: docker compose --project-directory . -f tests/e2e_tests/docker-compose-e2e-postgres.yml up -d
# 2. Run the tests using pytest.
# e.g. poetry run coverage run --branch -m pytest -s tests/e2e_tests/

# NOTE: to clean the database, run
# docker compose stop
# docker compose --project-directory . -f tests/e2e_tests/docker-compose-e2e-mysql.yml down --volumes
# docker compose --project-directory . -f tests/e2e_tests/docker-compose-e2e-postgres.yml down --volumes

import os
import random
import re
import string
import time
from datetime import datetime

from playwright.sync_api import Page, expect
import pytest

from tests.e2e_tests.incidents_alerts_tests.incidents_alerts_setup import (
    setup_incidents_alerts,
)
from tests.e2e_tests.utils import (
    assert_connected_provider_count,
    assert_scope_text_count,
    choose_combobox_option_with_retry,
    delete_provider,
    init_e2e_test,
    install_webhook_provider,
    save_failure_artifacts,
    setup_console_listener,
    trigger_alert,
)

# SHAHAR: you can uncomment locally, but keep in github actions
# NOTE 2: to run the tests with a browser, uncomment this two lines:
# os.environ["PLAYWRIGHT_HEADLESS"] = "false"

# Adding a new test:
# 1. Manually:
#    - Create a new test function.
#    - Use the `browser` fixture to interact with the browser.
# 2. Automatically:
#    - Spin up the environment using docker-compose.
#    - Run "playwright codegen localhost:3000" (unset DYLD_LIBRARY_PATH)
#    - Copy the generated code to a new test function.


def get_workflow_yaml(file_name):
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    with open(file_path, "r") as file:
        return file.read()


def close_all_toasts(page: Page):
    # First check if there are any toasts
    if page.locator(".Toastify__close-button").count() == 0:
        return

    # Try to close toasts with a shorter timeout and handle failures gracefully
    while page.locator(".Toastify__close-button").count() > 0:
        try:
            # Use first() to get the first toast and wait for it to be stable
            close_button = page.locator(".Toastify__close-button").first
            if close_button.is_visible():
                close_button.click(timeout=1000)
        except Exception:
            # If clicking fails (e.g. button disappeared), continue to next toast
            continue


def test_sanity(browser: Page):  # browser is actually a page object
    log_entries = []
    setup_console_listener(browser, log_entries)

    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        try:
            # Verify server is up
            init_e2e_test(browser, wait_time=1)

            # Now try the navigation with increased timeout
            # Ignore queryparams suchas tenantId
            browser.wait_for_url(
                re.compile(r"http://localhost:3000/incidents(\?.*)?"), timeout=15000
            )
            assert "Keep" in browser.title()

            # If we get here, the test passed
            return

        except Exception:
            attempt += 1
            if attempt >= max_attempts:
                # Final attempt failed, save artifacts and re-raise
                save_failure_artifacts(browser, log_entries)
                raise

            # Wait before retry
            time.sleep(2)


def test_insert_new_alert(browser: Page, setup_page_logging, failure_artifacts):
    """
    Test to insert a new alert
    """
    log_entries = []
    setup_console_listener(browser, log_entries)

    try:
        init_e2e_test(
            browser,
            next_url="/providers",
        )
        base_url = "http://localhost:3000/providers"
        url_pattern = re.compile(f"{re.escape(base_url)}(\\?.*)?$")
        browser.wait_for_url(url_pattern)

        feed_badge = browser.get_by_test_id("menu-alerts-feed-badge")
        feed_count_before = int(feed_badge.text_content() or "0")

        # now Keep avatar will look like "K) Keep (Keep12345)"
        browser.get_by_role("button", name="K) Keep").click()
        browser.get_by_role("menuitem", name="Settings").click()
        browser.get_by_role("tab", name="Webhook").click()
        browser.get_by_role("button", name="Click to create an example").click()
        # just wait a bit
        browser.wait_for_timeout(2000)
        # refresh the page
        browser.reload()
        # wait for badge counter to update
        browser.wait_for_timeout(500)
        feed_badge = browser.get_by_test_id("menu-alerts-feed-badge")
        feed_count = int(feed_badge.text_content() or "0")
        assert feed_count > feed_count_before

        feed_link = browser.get_by_test_id("menu-alerts-feed-link")
        feed_link.click()
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_providers_page_is_accessible(
    browser: Page, setup_page_logging, failure_artifacts
):
    """
    Test to check if the providers page is accessible

    """
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(
            browser,
            next_url="/signin?callbackUrl=http%3A%2F%2Flocalhost%3A3000%2Fproviders",
        )
        base_url = "http://localhost:3000/providers"
        url_pattern = re.compile(f"{re.escape(base_url)}(\\?.*)?$")
        browser.wait_for_url(url_pattern)
        # get the GCP Monitoring provider
        browser.locator("button:has-text('GCP Monitoring'):has-text('alert')").click()
        browser.get_by_role("button", name="Cancel").click()
        # connect resend provider
        browser.locator("button:has-text('Resend'):has-text('messaging')").click()
        browser.get_by_placeholder("Enter provider name").click()
        random_provider_name = "".join(
            [random.choice(string.ascii_letters) for i in range(10)]
        )
        browser.get_by_placeholder("Enter provider name").fill(random_provider_name)
        browser.get_by_placeholder("Enter provider name").press("Tab")
        browser.get_by_placeholder("Enter api_key").fill("bla")
        browser.get_by_role("button", name="Connect", exact=True).click()
        # wait a bit
        browser.wait_for_selector("text=Connected", timeout=15000)
        # make sure the provider is connected:
        # find and click the button containing the provider id in its nested elements
        provider_button = browser.locator(f"button:has-text('{random_provider_name}')")
        provider_button.click()
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_provider_validation(browser: Page, setup_page_logging, failure_artifacts):
    """
    Test field validation for provider fields.
    """
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        # using Kibana Provider
        browser.get_by_role("link", name="Providers").click()
        browser.locator("button:has-text('Kibana'):has-text('alert')").click()
        # test required fields
        connect_btn = browser.get_by_role("button", name="Connect", exact=True)
        cancel_btn = browser.get_by_role("button", name="Cancel", exact=True)
        error_msg = browser.locator("p.tremor-TextInput-errorMessage")
        connect_btn.click()
        expect(error_msg).to_have_count(3)
        cancel_btn.click()
        # test `any_http_url` field validation
        browser.locator("button:has-text('Kibana'):has-text('alert')").click()
        host_input = browser.get_by_placeholder("Enter kibana_host")
        host_input.fill("invalid url")
        expect(error_msg).to_have_count(1)
        host_input.fill("http://localhost")
        expect(error_msg).to_be_hidden()
        host_input.fill("https://keep.kb.us-central1.gcp.cloud.es.io")
        expect(error_msg).to_be_hidden()
        # test `port` field validation
        port_input = browser.get_by_placeholder("Enter kibana_port")
        port_input.fill("invalid port")
        expect(error_msg).to_have_count(1)
        port_input.fill("0")
        expect(error_msg).to_have_count(1)
        port_input.fill("65_536")
        expect(error_msg).to_have_count(1)
        port_input.fill("9243")
        expect(error_msg).to_be_hidden()
        cancel_btn.click()

        # using Teams Provider
        browser.locator("button:has-text('Teams'):has-text('messaging')").click()
        # test `https_url` field validation
        url_input = browser.get_by_placeholder("Enter webhook_url")
        url_input.fill("random url")
        expect(error_msg).to_have_count(1)
        url_input.fill("http://localhost")
        expect(error_msg).to_have_count(1)
        url_input.fill("http://example.com")
        expect(error_msg).to_have_count(1)
        url_input.fill("https://example.c")
        expect(error_msg).to_have_count(1)
        url_input.fill("https://example.com")
        expect(error_msg).to_be_hidden()
        cancel_btn.click()

        # using Site24x7 Provider
        browser.locator("button:has-text('Site24x7'):has-text('alert')").click()
        # test `tld` field validation
        tld_input = browser.get_by_placeholder("Enter zohoAccountTLD")
        tld_input.fill("random")
        expect(error_msg).to_have_count(1)
        tld_input.fill("")
        expect(error_msg).to_have_count(1)
        tld_input.fill(".com")
        expect(error_msg).to_be_hidden()
        cancel_btn.click()

        # using MongoDB Provider
        browser.locator("button:has-text('MongoDB'):has-text('data')").click()
        # test `multihost_url` field validation
        host_input = browser.get_by_placeholder("Enter host")
        host_input.fill("random")
        expect(error_msg).to_have_count(1)
        host_input.fill("host.com:5000")
        expect(error_msg).to_have_count(1)
        host_input.fill("host1.com:5000,host2.com:3000")
        expect(error_msg).to_have_count(1)
        host_input.fill("mongodb://host1.com:5000,mongodb+srv://host2.com:3000")
        expect(error_msg).to_have_count(1)
        host_input.fill("mongodb://host.com:3000")
        expect(error_msg).to_be_hidden()
        host_input.fill("mongodb://localhost:3000,localhost:5000")
        expect(error_msg).to_be_hidden()
        cancel_btn.click()

        # using Kafka Provider
        browser.locator("button:has-text('Kafka'):has-text('queue')").click()
        # test `no_scheme_multihost_url` field validation
        host_input = browser.get_by_placeholder("Enter host")
        host_input.fill("*.")
        expect(error_msg).to_have_count(1)
        host_input.fill("host.com:5000")
        expect(error_msg).to_be_hidden()
        host_input.fill("host1.com:5000,host2.com:3000")
        expect(error_msg).to_be_hidden()
        host_input.fill("http://host1.com:5000,https://host2.com:3000")
        expect(error_msg).to_have_count(1)
        host_input.fill("http://host.com:3000")
        expect(error_msg).to_be_hidden()
        host_input.fill("mongodb://localhost:3000,localhost:5000")
        expect(error_msg).to_be_hidden()
        cancel_btn.click()

        # using Postgres provider
        browser.get_by_role("link", name="Providers").click()
        browser.locator("button:has-text('PostgreSQL'):has-text('data')").click()
        # test `no_scheme_url` field validation
        host_input = browser.get_by_placeholder("Enter host")
        host_input.fill("*.")
        expect(error_msg).to_have_count(1)
        host_input.fill("localhost:5000")
        expect(error_msg).to_be_hidden()
        host_input.fill("https://host.com:3000")
        expect(error_msg).to_be_hidden()
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_provider_deletion(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)
    provider_name = "playwright_test_" + datetime.now().strftime("%Y%m%d%H%M%S")
    try:

        # Checking deletion after Creation
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Providers").hover()
        browser.get_by_role("link", name="Providers").click()
        install_webhook_provider(
            browser=browser,
            provider_name=provider_name,
            webhook_url="http://keep-backend:8080",
            webhook_action="GET",
        )
        browser.wait_for_timeout(500)
        assert_connected_provider_count(
            browser=browser,
            provider_type="Webhook",
            provider_name=provider_name,
            provider_count=1,
        )
        delete_provider(
            browser=browser, provider_type="Webhook", provider_name=provider_name
        )
        assert_connected_provider_count(
            browser=browser,
            provider_type="Webhook",
            provider_name=provider_name,
            provider_count=0,
        )

        # Checking deletion after Creation + Updation
        install_webhook_provider(
            browser=browser,
            provider_name=provider_name,
            webhook_url="http://keep-backend:8080",
            webhook_action="GET",
        )
        browser.wait_for_timeout(500)
        assert_connected_provider_count(
            browser=browser,
            provider_type="Webhook",
            provider_name=provider_name,
            provider_count=1,
        )
        # Updating provider
        browser.locator(
            f"button:has-text('Webhook'):has-text('Connected'):has-text('{provider_name}')"
        ).click()
        browser.get_by_placeholder("Enter url").clear()
        # Use a blacklisted URL to trigger validation error
        browser.get_by_placeholder("Enter url").fill("https://metadata.google.internal/test")

        browser.get_by_role("button", name="Update", exact=True).click()
        browser.wait_for_timeout(500)
        # Refreshing the scope
        browser.get_by_role("button", name="Validate Scopes", exact=True).click()
        browser.wait_for_timeout(500)
        assert_scope_text_count(
            browser=browser, contains_text="blacklisted", count=1
        )
        browser.mouse.click(10, 10)
        delete_provider(
            browser=browser, provider_type="Webhook", provider_name=provider_name
        )
        assert_connected_provider_count(
            browser=browser,
            provider_type="Webhook",
            provider_name=provider_name,
            provider_count=0,
        )
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_add_workflow(browser: Page, setup_page_logging, failure_artifacts):
    """
    Test to add a workflow node
    """
    page = browser
    log_entries = []
    setup_console_listener(page, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        page.get_by_role("link", name="Workflows").click()
        page.get_by_role("button", name="Start from scratch").click()
        page.get_by_placeholder("Set the name").click()
        page.get_by_placeholder("Set the name").press("ControlOrMeta+a")
        page.get_by_placeholder("Set the name").fill("Example Console Workflow")
        page.get_by_placeholder("Set the name").press("Tab")
        page.get_by_placeholder("Set the description").fill(
            "Example workflow description"
        )
        page.get_by_test_id("wf-add-trigger-button").first.click()
        page.get_by_text("Manual").click()
        page.get_by_test_id("wf-add-step-button").first.click()
        page.get_by_placeholder("Search...").click()
        page.get_by_placeholder("Search...").fill("cons")
        page.get_by_text("console-action").click()
        page.wait_for_timeout(500)
        page.locator(".react-flow__node:has-text('console-action')").click()
        page.get_by_placeholder("message", exact=True).click()
        page.get_by_placeholder("message", exact=True).fill("Hello world!")
        page.get_by_test_id("wf-editor-configure-save-button").click()
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        expect(page.get_by_test_id("wf-name")).to_contain_text(
            "Example Console Workflow"
        )
        expect(page.get_by_test_id("wf-description")).to_contain_text(
            "Example workflow description"
        )
        expect(page.get_by_test_id("wf-revision").first).to_contain_text("Revision 1")
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_test_run_workflow(browser: Page):
    """
    Test to test run a workflow
    """
    page = browser
    log_entries = []
    setup_console_listener(page, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        page.get_by_role("link", name="Workflows").click()
        page.wait_for_url("**/workflows")
        page.wait_for_timeout(500)

        if page.locator('[data-testid="workflows-exist-state"]').is_visible():
            page.get_by_role("button", name="Create workflow").click()
            page.get_by_role("button", name="Start from scratch").click()
        elif page.locator('[data-testid="no-workflows-state"]').is_visible():
            page.get_by_role("button", name="Start from scratch").click()
        else:
            raise Exception("Unknown state is visible for workflows page")

        page.wait_for_url("http://localhost:3000/workflows/builder")
        page.get_by_placeholder("Set the name").click()
        page.get_by_placeholder("Set the name").press("ControlOrMeta+a")
        page.get_by_placeholder("Set the name").fill("Test Run Workflow")
        page.get_by_placeholder("Set the name").press("Tab")
        page.get_by_placeholder("Set the description").fill(
            "Test Run workflow description"
        )
        page.get_by_test_id("wf-add-trigger-button").first.click()
        page.get_by_text("Manual").click()
        page.get_by_test_id("wf-add-step-button").first.click()
        page.get_by_placeholder("Search...").click()
        page.get_by_placeholder("Search...").fill("cons")
        page.get_by_text("console-action").click()
        page.get_by_placeholder("message", exact=True).click()
        page.get_by_placeholder("message", exact=True).fill("Hello world!")
        page.get_by_test_id("wf-editor-configure-save-button").click()
        page.wait_for_url(re.compile(r"http://localhost:3000/workflows/(?!builder).*"))
        page.get_by_text("Builder").click()
        page.get_by_test_id("wf-builder-main-test-run-button").click()
        page.wait_for_selector("text=Workflow Execution Results")
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_paste_workflow_yaml_quotes_preserved(browser: Page):
    # browser is actually a page object
    page = browser

    log_entries = []
    setup_console_listener(page, log_entries)

    workflow_yaml = get_workflow_yaml("workflow-quotes-sample.yaml")

    try:
        init_e2e_test(browser, next_url="/workflows")
        page.get_by_role("button", name="Upload Workflows").click()
        page.get_by_test_id("text-area").click()
        page.get_by_test_id("text-area").fill(workflow_yaml)
        page.get_by_role("button", name="Load", exact=True).click()
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        page.get_by_role("tab", name="YAML Definition").click()
        yaml_editor_container = page.get_by_test_id("wf-detail-yaml-editor-container")
        # Copy the YAML content to the clipboard
        yaml_editor_container.get_by_test_id("copy-yaml-button").click()
        # Get the clipboard content
        clipboard_text = page.evaluate(
            """async () => {
            return await navigator.clipboard.readText();
        }"""
        )
        # Remove all whitespace characters from the YAML content for comparison
        normalized_original = re.sub(r"\s", "", workflow_yaml)
        normalized_clipboard = re.sub(r"\s", "", clipboard_text)
        assert normalized_clipboard == normalized_original
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_add_upload_workflow_with_alert_trigger(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/workflows")
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-sample.yaml")
        browser.get_by_role("button", name="Upload")
        # new behavior: is redirecting to the detail page of the workflow, so we need to go back to the list page
        expect(browser.locator("a", has_text="Workflow Details")).to_be_visible()
        expect(browser.locator("[data-testid='wf-name']")).to_have_text(
            "test_add_upload_workflow_with_alert_trigger"
        )
        browser.wait_for_timeout(500)
        trigger_alert("prometheus")
        browser.wait_for_timeout(2000)
        browser.goto("http://localhost:3000/workflows")
        # wait for prometheus to fire an alert and workflow to run
        browser.reload()
        workflow_card = browser.locator(
            "[data-testid^='workflow-tile-']",
            has_text="test_add_upload_workflow_with_alert_trigger",
        )
        expect(workflow_card).not_to_contain_text("No data available")
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_monaco_editor_npm(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        browser.route(
            "**/*",
            lambda route, request: (
                route.abort()
                if not request.url.startswith("http://localhost")
                else route.continue_()
            ),
        )
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-sample-npm.yaml")
        browser.get_by_role("button", name="Upload")
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        browser.get_by_role("tab", name="YAML Definition").click()
        editor_container = browser.get_by_test_id("wf-detail-yaml-editor-container")
        expect(editor_container).not_to_contain_text(
            "Error loading Monaco Editor from CDN"
        )
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_yaml_editor_yaml_valid(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)

    try:
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-valid-sample.yaml")
        browser.get_by_role("button", name="Upload")
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        browser.get_by_role("tab", name="YAML Definition").click()
        yaml_editor = browser.get_by_test_id("wf-detail-yaml-editor-container")
        expect(yaml_editor).to_be_visible()
        expect(
            yaml_editor.get_by_test_id(
                "wf-yaml-editor-validation-errors-no-errors"
            ).first
        ).to_be_visible()
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_yaml_editor_yaml_invalid(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)

    try:
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-invalid-sample.yaml")
        browser.get_by_role("button", name="Upload")
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        browser.get_by_role("tab", name="YAML Definition").click()
        yaml_editor = browser.get_by_test_id("wf-detail-yaml-editor-container")
        expect(yaml_editor).to_be_visible()
        errors_list = yaml_editor.get_by_test_id(
            "wf-yaml-editor-validation-errors-list"
        ).first
        summary = yaml_editor.get_by_test_id(
            "wf-yaml-editor-validation-errors-summary"
        ).first
        summary.click()
        expect(summary).to_contain_text("11 validation errors")
        expect(errors_list).to_contain_text(
            "String is shorter than the minimum length of 1."
        )
        expect(errors_list).to_contain_text('Missing property "provider".')
        expect(errors_list).to_contain_text(
            "Property provider_invalid_prop is not allowed."
        )
        expect(errors_list).to_contain_text(
            "Property message_invalid_prop is not allowed."
        )
        expect(errors_list).to_contain_text("Property enrich_incident is not allowed.")
        expect(errors_list).to_contain_text("Property enrich_alert is not allowed.")
        expect(errors_list).to_contain_text(
            re.compile(
                r"Variable.*steps\.clickhouse-step\.results\.level.*step doesn\'t exist"
            )
        )

    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_workflow_inputs(browser: Page):
    page = browser
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/workflows")
        page.get_by_role("button", name="Upload Workflows").click()
        file_input = page.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-inputs-alert.yaml")
        page.get_by_role("button", name="Upload")
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        page.get_by_test_id("wf-run-now-button").click()
        page.locator("div").filter(
            has_text=re.compile(
                r"^nodefault \*A no default examplesThis field is required$"
            )
        ).get_by_role("textbox").fill("shalom")
        page.get_by_role("button", name="Run", exact=True).click()
        alert_dependencies_form = page.get_by_test_id("wf-alert-dependencies-form")
        expect(alert_dependencies_form).to_be_visible()
        alert_dependencies_form.locator("input[name='name']").fill("GrafanaDown")
        alert_dependencies_form.get_by_test_id(
            "wf-alert-dependencies-form-submit"
        ).click()
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*/runs/.*"))
        page.get_by_role("button", name="Running action echo 0s").click()
        expect(page.locator(".bg-gray-100 > .overflow-auto").first).to_contain_text(
            "Input Nodefault: shalom"
        )
        expect(page.locator(".bg-gray-100 > .overflow-auto").first).to_contain_text(
            "Alert Name: GrafanaDown"
        )
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_workflow_test_run(browser: Page):
    page = browser
    log_entries = []
    setup_console_listener(browser, log_entries)
    yaml_content = get_workflow_yaml("workflow-inputs-alert.yaml")
    try:
        init_e2e_test(browser, next_url="/signin")
        page.goto("http://localhost:3000/workflows")
        page.get_by_role("button", name="Create workflow").click()
        page.get_by_role("button", name="Start from scratch").click()
        page.get_by_test_id("wf-open-editor-button").click()
        editor = page.get_by_test_id("wf-builder-yaml-editor").locator(".monaco-editor")
        editor.click()
        page.keyboard.press("ControlOrMeta+KeyA")
        page.keyboard.press("Backspace")
        page.evaluate(
            """async (text) => {
            return await navigator.clipboard.writeText(text);
        }""",
            yaml_content,
        )
        page.keyboard.press("ControlOrMeta+KeyV")
        page.wait_for_timeout(500)
        page.get_by_test_id("wf-builder-main-test-run-button").click()
        # Fill inputs
        page.locator("div").filter(
            has_text=re.compile(
                r"^nodefault \*A no default examplesThis field is required$"
            )
        ).get_by_role("textbox").fill("shalom")
        page.get_by_role("button", name="Run", exact=True).click()
        # Fill alert dependencies
        alert_dependencies_form = page.get_by_test_id("wf-alert-dependencies-form")
        expect(alert_dependencies_form).to_be_visible()
        alert_dependencies_form.locator("input[name='name']").fill("GrafanaDown")
        alert_dependencies_form.get_by_test_id(
            "wf-alert-dependencies-form-submit"
        ).click()
        results = page.get_by_test_id("wf-test-run-results")
        expect(results).to_be_visible()
        results.get_by_role("button", name="Running action echo").click()
        expect(results).to_contain_text("GrafanaDown")
        expect(results).not_to_contain_text("Failed to run step")
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_workflow_unsaved_changes(browser: Page):
    page = browser
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        page.goto("http://localhost:3000/workflows")
        page.get_by_role("button", name="Upload Workflows").click()
        file_input = page.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-inputs.yaml")
        page.get_by_role("button", name="Upload")
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        page.get_by_role("tab", name="Builder").click()
        page.locator("[data-testid='workflow-node']").filter(has_text="echo").click()
        page.get_by_test_id("wf-editor-step-name-input").click()
        page.get_by_test_id("wf-editor-step-name-input").fill("echo-test")
        page.wait_for_timeout(300)
        page.get_by_test_id("wf-run-now-button").click()
        unsaved_ui_form = page.get_by_test_id("wf-ui-unsaved-changes-form")
        expect(unsaved_ui_form).to_be_visible()
        unsaved_ui_form.get_by_test_id("wf-unsaved-changes-save-and-run").click()
        page.locator("div").filter(
            has_text=re.compile(
                r"^nodefault \*A no default examplesThis field is required$"
            )
        ).get_by_role("textbox").fill("shalom")
        page.get_by_role("button", name="Run", exact=True).click()
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*/runs/.*"))
        log_step = page.get_by_role("button", name="Running action echo-test")
        expect(log_step).to_be_visible()
        close_all_toasts(page)
        page.get_by_role("link", name="Workflow Details").click()
        page.get_by_role("tab", name="YAML Definition").click()
        page.get_by_test_id("wf-detail-yaml-editor").get_by_label(
            "Editor content"
        ).fill("random string")
        page.get_by_test_id("wf-run-now-button").click()
        yaml_unsaved_form = page.get_by_test_id("wf-yaml-unsaved-changes-form")
        expect(yaml_unsaved_form).to_be_visible()
        yaml_unsaved_form.get_by_test_id("wf-unsaved-changes-discard-and-run").click()
        page.locator("div").filter(
            has_text=re.compile(
                r"^nodefault \*A no default examplesThis field is required$"
            )
        ).get_by_role("textbox").fill("shalom")
        page.get_by_test_id("wf-inputs-form-submit").click()
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*/runs/.*"))
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


@pytest.fixture(scope="module")
def setup_alerts_and_incidents():
    print("Setting up alerts and incidents...")
    test_data = setup_incidents_alerts()
    yield test_data


def test_run_workflow_from_alert_and_incident(
    browser: Page, setup_alerts_and_incidents
):
    page = browser
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/workflows")
        page.get_by_role("button", name="Upload Workflows").click()
        file_input = page.locator("#workflowFile")
        file_input.set_input_files(
            [
                "./tests/e2e_tests/workflow-alert-log.yaml",
                "./tests/e2e_tests/workflow-incident-log.yaml",
            ]
        )
        page.get_by_role("button", name="Upload")
        expect(page.get_by_text("2 workflows uploaded successfully")).to_be_visible()
        # Run workflow from incident
        page.locator("[data-testid='incidents-link']").click()
        # wait for the incidents facets to load, so it doesn't interfere with the dropdown
        page.wait_for_selector("[data-testid='facet-value']")
        page.wait_for_timeout(500)
        page.get_by_test_id("incidents-table").get_by_test_id(
            "dropdown-menu-button"
        ).first.click()
        page.get_by_test_id("dropdown-menu-list").get_by_role(
            "button", name="Run workflow"
        ).click()
        modal = page.get_by_test_id("manual-run-workflow-modal")
        page.wait_for_timeout(200)
        expect(modal).to_be_visible()
        page.wait_for_timeout(200)
        select = modal.get_by_test_id("manual-run-workflow-select-control")
        choose_combobox_option_with_retry(page, select, "Log every incident")
        modal.get_by_role("button", name="Run").click()
        expect(page.get_by_text("Workflow started successfully")).to_be_visible()
        # Run workflow from alert
        page.locator("[data-testid='menu-alerts-feed-link']").click()
        # wait for the alerts facets to load, so it doesn't interfere with the dropdown
        page.wait_for_selector("[data-testid='facet-value']")
        page.wait_for_timeout(500)
        page.get_by_test_id("alerts-table").locator(
            "[data-column-id='alertMenu']"
        ).first.get_by_test_id("dropdown-menu-button").click()
        page.get_by_test_id("dropdown-menu-list").get_by_role(
            "button", name="Run workflow"
        ).click()
        modal = page.get_by_test_id("manual-run-workflow-modal")
        select = modal.get_by_test_id("manual-run-workflow-select-control")
        choose_combobox_option_with_retry(page, select, "Log every alert")
        modal.get_by_role("button", name="Run").click()
        expect(page.get_by_text("Workflow started successfully")).to_be_visible()
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_run_interval_workflow(browser: Page):
    page = browser
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/workflows")
        page.get_by_role("button", name="Upload Workflows").click()
        file_input = page.locator("#workflowFile")
        file_input.set_input_files(
            [
                "./tests/e2e_tests/workflow-interval.yaml",
            ]
        )
        page.get_by_role("button", name="Upload")
        expect(page.get_by_text("1 workflow uploaded successfully")).to_be_visible()
        page.wait_for_timeout(
            10000
        )  # wait 10 seconds to let interval workflow run few times
        page.reload()
        rows = page.locator("table tr", has_text="Interval workflow")
        expect(rows).not_to_have_count(0)
        executions_count = rows.count()
        assert executions_count >= 4 and executions_count <= 8

    except Exception:
        save_failure_artifacts(page, log_entries)
        raise
