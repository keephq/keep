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
from datetime import datetime

import pytest
from playwright.sync_api import expect

# Running the tests in GitHub Actions:
# - Look at the test-pr-e2e.yml file in the .github/workflows directory.


# os.environ["PLAYWRIGHT_HEADLESS"] = "false"


@pytest.fixture(scope="session")
def browserx():
    from playwright.sync_api import sync_playwright

    headless = False
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(5000)
        yield page
        context.close()
        browser.close()

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
        browser.wait_for_url("http://localhost:3000/incidents")

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
    try:
        browser.goto(
            "http://localhost:3000/signin?callbackUrl=http%3A%2F%2Flocalhost%3A3000%2Fproviders"
        )
        browser.goto("http://localhost:3000/providers")
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
        # Current file + test name for unique html and png dump.
        current_test_name = (
            "playwright_dump_"
            + os.path.basename(__file__)[:-3]
            + "_"
            + sys._getframe().f_code.co_name
        )

        browser.screenshot(path=current_test_name + ".png")
        with open(current_test_name + ".html", "w") as f:
            f.write(browser.content())
        raise


def test_provider_validation(browser):
    """
    Test field validation for provider fields.
    """
    # browser = browserx
    browser.goto("http://localhost:3000/signin")
    # browser.goto("http://localhost:3000/providers")
    # using Kibana Provider
    browser.get_by_role("link", name="Providers").click()
    browser.locator("button:has-text('Kibana'):has-text('alert')").click()
    # test required fields
    connect_btn = browser.get_by_role("button", name="Connect", exact=True)
    cancel_btn = browser.get_by_role("button", name="Cancel", exact=True)
    error_msg = browser.locator("p.tremor-TextInput-errorMessage")
    connect_btn.click()
    expect(error_msg).to_have_count(3)
    # test `any_http_url` field validation
    browser.get_by_placeholder("Enter provider name").fill("random name")
    browser.get_by_placeholder("Enter api_key").fill("random api key")
    browser.get_by_placeholder("Enter kibana_host").fill("invalid url")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter kibana_host").fill("http://localhost")
    expect(error_msg).to_be_hidden()
    browser.get_by_placeholder("Enter kibana_host").fill(
        "https://keep.kb.us-central1.gcp.cloud.es.io"
    )
    expect(error_msg).to_be_hidden()
    # test `port` field validation
    browser.get_by_placeholder("Enter kibana_port").fill("invalid port")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter kibana_port").fill("0")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter kibana_port").fill("65_536")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter kibana_port").fill("9243")
    expect(error_msg).to_be_hidden()
    cancel_btn.click()

    # using Teams Provider
    browser.locator("button:has-text('Teams'):has-text('messaging')").click()
    # test `https_url` field validation
    browser.get_by_placeholder("Enter provider name").fill("random name")
    browser.get_by_placeholder("Enter webhook_url").fill("random url")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter webhook_url").fill("http://localhost")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter webhook_url").fill("http://example.com")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter webhook_url").fill("https://example.com")
    expect(error_msg).to_be_hidden()
    cancel_btn.click()

    # using Site24x7 Provider
    browser.locator("button:has-text('Site24x7'):has-text('alert')").click()
    # test `tld` field validation
    browser.get_by_placeholder("Enter provider name").fill("random name")
    browser.get_by_placeholder("Enter zohoRefreshToken").fill("random")
    browser.get_by_placeholder("Enter zohoClientId").fill("random")
    browser.get_by_placeholder("Enter zohoClientSecret").fill("random")
    browser.get_by_placeholder("Enter zohoAccountTLD").fill("random")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter zohoAccountTLD").fill("")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter zohoAccountTLD").fill(".com")
    expect(error_msg).to_be_hidden()
    cancel_btn.click()

    # using MongoDB Provider
    browser.locator("button:has-text('MongoDB'):has-text('data')").click()
    # test `any_url` field validation
    browser.get_by_placeholder("Enter provider name").fill("random name")
    browser.get_by_placeholder("Enter host").fill("random")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter host").fill("host.com:5000")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter host").fill("mongodb://host.com:3000")
    expect(error_msg).to_be_hidden()
    cancel_btn.click()

    # using Postgres provider
    browser.get_by_role("link", name="Providers").click()
    browser.locator("button:has-text('PostgreSQL'):has-text('data')").click()
    # test `no_scheme_url` field validation
    # - on the frontend: url with/without scheme validates.
    # - on the backend: scheme is removed during validation.
    browser.get_by_placeholder("Enter provider name").fill("random name")
    browser.get_by_placeholder("Enter username").fill("username")
    browser.get_by_placeholder("Enter password").fill("password")
    browser.get_by_placeholder("Enter host").fill("*.")
    expect(error_msg).to_have_count(1)
    browser.get_by_placeholder("Enter host").fill("localhost:5000")
    expect(error_msg).to_be_hidden()
    browser.get_by_placeholder("Enter host").fill("https://host.com:3000")
    expect(error_msg).to_be_hidden()
