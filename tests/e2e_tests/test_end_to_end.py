# This file contains the end-to-end tests for Keep.

# There are two mode of operations:
# 1. Running the tests locally
# 2. Running the tests in GitHub Actions

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
# NOTE 2: to run the tests with a browser, uncomment this:
# import os

# os.environ["PLAYWRIGHT_HEADLESS"] = "false"

# Running the tests in GitHub Actions:
# - Look at the test-pr-e2e.yml file in the .github/workflows directory.

import os
import random

# Adding a new test:
# 1. Manually:
#    - Create a new test function.
#    - Use the `browser` fixture to interact with the browser.
# 2. Automatically:
#    - Spin up the environment using docker-compose.
#    - Run "playwright codegen localhost:3000"
#    - Copy the generated code to a new test function.
import string
import sys
import re
from datetime import datetime
import requests
from tests.e2e_tests.utils import trigger_alert

from playwright.sync_api import expect

from tests.e2e_tests.utils import install_webhook_provider, delete_provider, assert_connected_provider_count, assert_scope_text_count

# Running the tests in GitHub Actions:
# - Look at the test-pr-e2e.yml file in the .github/workflows directory.


# os.environ["PLAYWRIGHT_HEADLESS"] = "false"


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


def save_failure_artifacts(page, log_entries):
    """Save screenshots, HTML content, and console logs on test failure."""
    # Generate unique name for the dump files
    current_test_name = (
        "playwright_dump_"
        + os.path.basename(__file__)[:-3]
        + "_"
        + sys._getframe().f_code.co_name
    )

    # Save screenshot
    page.screenshot(path=current_test_name + ".png")

    # Save HTML content
    with open(current_test_name + ".html", "w", encoding="utf-8") as f:
        f.write(page.content())

    # Save console logs
    with open(current_test_name + "_console.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log_entries))


def test_sanity(browser):  # browser is actually a page object
    log_entries = []
    setup_console_listener(browser, log_entries)

    try:
        browser.goto("http://localhost:3000/")
        browser.wait_for_url("http://localhost:3000/incidents")
        assert "Keep" in browser.title()
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_insert_new_alert(browser):  # browser is actually a page object
    """
    Test to insert a new alert
    """
    log_entries = []
    setup_console_listener(browser, log_entries)

    try:
        browser.goto(
            "http://localhost:3000/signin?callbackUrl=http%3A%2F%2Flocalhost%3A3000%2Fproviders"
        )
        browser.wait_for_url("http://localhost:3000/providers")

        feed_badge = browser.get_by_test_id("menu-alerts-feed-badge")
        feed_count_before = int(feed_badge.text_content())

        browser.get_by_role("button", name="KE Keep").click()
        browser.get_by_role("menuitem", name="Settings").click()
        browser.get_by_role("tab", name="Webhook").click()
        browser.get_by_role("button", name="Click to create an example").click()
        # just wait a bit
        browser.wait_for_timeout(10000)
        # refresh the page
        browser.reload()
        # wait for badge counter to update
        browser.wait_for_timeout(500)
        feed_badge = browser.get_by_test_id("menu-alerts-feed-badge")
        feed_count = int(feed_badge.text_content())
        assert feed_count > feed_count_before

        feed_link = browser.get_by_test_id("menu-alerts-feed-link")
        feed_link.click()

    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_providers_page_is_accessible(browser):
    """
    Test to check if the providers page is accessible

    """
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        browser.goto(
            "http://localhost:3000/signin?callbackUrl=http%3A%2F%2Flocalhost%3A3000%2Fproviders"
        )
        browser.wait_for_url("http://localhost:3000/providers")
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


def test_provider_validation(browser):
    """
    Test field validation for provider fields.
    """
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        browser.goto("http://localhost:3000/signin")
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


def test_add_workflow(browser):
    """
    Test to add a workflow node
    """
    # browser is actually a page object
    page = browser
    log_entries = []
    setup_console_listener(page, log_entries)
    try:
        page.goto("http://localhost:3000/signin")
        page.get_by_role("link", name="Workflows").click()
        page.get_by_role("button", name="Create a workflow").click()
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
        page.get_by_placeholder("message").click()
        page.get_by_placeholder("message").fill("Hello world!")
        page.get_by_role("button", name="Save & Deploy").click()
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


def test_add_upload_workflow_with_alert_trigger(browser):
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        browser.goto("http://localhost:3000/signin")
        browser.get_by_role("link", name="Workflows").hover()
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        browser.wait_for_timeout(5000)
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files(
            "./tests/e2e_tests/workflow-sample.yaml"
        )
        browser.get_by_role("button", name="Upload")
        browser.wait_for_timeout(10000)
        trigger_alert("prometheus")
        browser.wait_for_timeout(3000)
        browser.reload()
        browser.wait_for_timeout(3000)
        workflow_card = browser.locator(
            "[data-sentry-component='WorkflowTile']",
            has_text="9b3664f4-b248-4eda-8cc7-e69bc5a8bd92",
        )
        expect(workflow_card).not_to_contain_text("No data available")
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise


def test_start_with_keep_db(browser):
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        browser.goto("http://localhost:3001/signin")
        browser.wait_for_timeout(3000)
        browser.get_by_placeholder("Enter your username").fill("keep")
        browser.get_by_placeholder("Enter your password").fill("keep")
        browser.wait_for_timeout(3000)
        browser.get_by_role("button", name="Sign in").click()
        browser.wait_for_timeout(5000)
        expect(browser).to_have_url("http://localhost:3001/incidents")
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise

def test_provider_deletion(browser):
    log_entries = []
    setup_console_listener(browser, log_entries)
    provider_name = "playwright_test_" + datetime.now().strftime("%Y%m%d%H%M%S")
    try:

        # Checking deletion after Creation 
        browser.goto("http://localhost:3000/signin")
        browser.get_by_role("link", name="Providers").hover()
        browser.get_by_role("link", name="Providers").click()
        browser.wait_for_timeout(10000)
        install_webhook_provider(browser=browser, provider_name=provider_name, webhook_url="http://keep-backend:8080", webhook_action="GET")
        browser.wait_for_timeout(2000)
        assert_connected_provider_count(browser=browser, provider_type="Webhook", provider_name=provider_name, provider_count=1)
        delete_provider(browser=browser, provider_type="Webhook", provider_name=provider_name)
        assert_connected_provider_count(browser=browser, provider_type="Webhook", provider_name=provider_name, provider_count=0)

        # Checking deletion after Creation + Updation
        install_webhook_provider(browser=browser, provider_name=provider_name, webhook_url="http://keep-backend:8080", webhook_action="GET")
        browser.wait_for_timeout(2000)
        assert_connected_provider_count(browser=browser, provider_type="Webhook", provider_name=provider_name, provider_count=1)
        # Updating provider
        browser.locator(
            f"button:has-text('Webhook'):has-text('Connected'):has-text('{provider_name}')"
        ).click()
        browser.get_by_placeholder("Enter url").clear()
        browser.get_by_placeholder("Enter url").fill("https://this_is_UwU")

        browser.get_by_role("button", name="Update", exact=True).click()
        browser.wait_for_timeout(3000)
        # Refreshing the scope
        browser.get_by_role("button", name="Refresh", exact=True).click()
        browser.wait_for_timeout(3000)
        assert_scope_text_count(browser=browser, contains_text="HTTPSConnectionPool", count=1)
        browser.mouse.click(10, 10)
        delete_provider(browser=browser, provider_type="Webhook", provider_name=provider_name)
        assert_connected_provider_count(browser=browser, provider_type="Webhook", provider_name=provider_name, provider_count=0)

    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise
