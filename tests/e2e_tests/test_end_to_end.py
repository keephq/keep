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

from tests.e2e_tests.utils import (
    assert_connected_provider_count,
    assert_scope_text_count,
    delete_provider,
    init_e2e_test,
    install_webhook_provider,
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
#    - Run "playwright codegen localhost:3000"
#    - Copy the generated code to a new test function.


def setup_console_listener(page, log_entries):
    """Set up console listener to capture logs."""
    page.on(
        "console",
        lambda msg: (
            log_entries.append(
                f"{datetime.now()}: {msg.text}, location: {msg.location}"
            )
        ),
    )


def save_failure_artifacts(browser, log_entries=None):
    # Get the current test name from pytest
    current_test_name = None
    try:
        # https://docs.pytest.org/en/latest/example/simple.html#pytest-current-test-environment-variable
        current_test_name = (
            os.environ.get("PYTEST_CURRENT_TEST").split(":")[-1].split(" ")[0]
        )
    except (AttributeError, IndexError, KeyError):
        # Fallback method if pytest environment variable isn't available
        current_test_name = "unknown_test"

    # Create the screenshot filename
    screenshot_filename = f"playwright_dump_{current_test_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"

    try:
        browser.screenshot(path=screenshot_filename)
        print(f"Screenshot saved: {screenshot_filename}")
    except Exception as e:
        print(f"Failed to save screenshot: {e}")

    # Save logs if provided
    if log_entries:
        logs_filename = f"console_logs_{current_test_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}.txt"
        try:
            with open(logs_filename, "w") as f:
                f.write("\n".join(str(log) for log in log_entries))
            print(f"Console logs saved: {logs_filename}")
        except Exception as e:
            print(f"Failed to save console logs: {e}")


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


def test_insert_new_alert(browser: Page):  # browser is actually a page object
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

        browser.get_by_role("button", name="KE Keep").click()
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


def test_providers_page_is_accessible(browser: Page):
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


def test_provider_validation(browser: Page):
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


def test_add_workflow(browser: Page):
    """
    Test to add a workflow node
    """
    # browser is actually a page object
    page = browser
    log_entries = []
    setup_console_listener(page, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        page.get_by_role("link", name="Workflows").click()
        page.get_by_role("button", name="Create Workflow").click()
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
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_paste_workflow_yaml_quotes_preserved(browser: Page):
    # browser is actually a page object
    page = browser
    log_entries = []
    setup_console_listener(page, log_entries)

    def get_workflow_yaml(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
        with open(file_path, "r") as file:
            return file.read()

    workflow_yaml = get_workflow_yaml("workflow-quotes-sample.yaml")

    try:
        init_e2e_test(browser, next_url="/workflows")
        page.get_by_role("button", name="Upload Workflows").click()
        page.get_by_test_id("text-area").click()
        page.get_by_test_id("text-area").fill(workflow_yaml)
        page.get_by_role("button", name="Load").click()
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
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Workflows").hover()
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-sample.yaml")
        browser.get_by_role("button", name="Upload")
        browser.wait_for_timeout(500)
        trigger_alert("prometheus")
        browser.wait_for_timeout(2000)
        # new behavior: is redirecting to the detail page of the workflow, so we need to go back to the list page
        browser.goto("http://localhost:3000/workflows")
        workflow_card = browser.locator(
            "[data-testid^='workflow-tile-']",
            has_text="9b3664f4-b248-4eda-8cc7-e69bc5a8bd92",
        )
        expect(workflow_card).not_to_contain_text("No data available")
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_start_with_keep_db(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        browser.goto("http://localhost:3001/signin")
        browser.get_by_placeholder("Enter your username").fill("keep")
        browser.get_by_placeholder("Enter your password").fill("keep")
        browser.get_by_role("button", name="Sign in").click()
        browser.wait_for_url("http://localhost:3001/incidents")
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
        browser.get_by_placeholder("Enter url").fill("https://this_is_UwU")

        browser.get_by_role("button", name="Update", exact=True).click()
        browser.wait_for_timeout(500)
        # Refreshing the scope
        browser.get_by_role("button", name="Refresh", exact=True).click()
        browser.wait_for_timeout(500)
        assert_scope_text_count(
            browser=browser, contains_text="HTTPSConnectionPool", count=1
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
