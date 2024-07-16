# This file contains the end-to-end tests for Keep.

# There are two mode of operations:
# 1. Running the tests locally
# 2. Running the tests in GitHub Actions

# Running the tests locally:
# 1. Spin up the environment using docker-compose.
#   for mysql: docker-compose --project-directory . -f tests/e2e_tests/docker-compose-e2e-mysql.yml up -d
#   for postgres: docker-compose --project-directory . -f tests/e2e_tests/docker-compose-e2e-postgres.yml up -d
# 2. Run the tests using pytest.
# NOTE: to clean the database, run docker volume rm keep_postgres_data keep_mysql-data
# NOTE 2: to run the tests with a browser, uncomment this:
# import os

# os.environ["PLAYWRIGHT_HEADLESS"] = "false"

# Running the tests in GitHub Actions:
# - Look at the test-pr-e2e.yml file in the .github/workflows directory.

import random

# Adding a new test:
# 1. Manually:
#    - Create a new test function.
#    - Use the `browser` fixture to interact with the browser.
# 2. Automatically:
#    - Spin up the environment using docker-compose.
#    - Run "playwright codegen localhost:3000"
#    - Copy the generated code to a new test function.
import re, os, sys
import string

# Running the tests in GitHub Actions:
# - Look at the test-pr-e2e.yml file in the .github/workflows directory.


# os.environ["PLAYWRIGHT_HEADLESS"] = "false"


def test_sanity(browser):
    browser.goto("http://localhost:3000/providers")
    browser.wait_for_url("http://localhost:3000/providers")
    assert "Keep" in browser.title()


def test_insert_new_alert(browser):
    """
    Test to insert a new alert

    """
    try:
        browser.goto(
            "http://localhost:3000/signin?callbackUrl=http%3A%2F%2Flocalhost%3A3000%2Fproviders"
        )
        browser.goto("http://localhost:3000/providers")
        browser.get_by_role("button", name="KE Keep").click()
        browser.get_by_role("menuitem", name="Settings").click()
        browser.get_by_role("tab", name="Webhook").click()
        browser.get_by_role("button", name="Click to create an example").click()
        # just wait a bit
        browser.wait_for_timeout(10000)
        # refresh the page
        browser.reload()
        browser.get_by_text("1", exact=True).click()
    except Exception:
        # Current file + test name for unique html and png dump.
        current_test_name = \
            "playwright_dump_" + \
            os.path.basename(__file__)[:-3] + \
            "_" + sys._getframe().f_code.co_name

        browser.screenshot(path=current_test_name + ".png")
        with open(current_test_name + ".html", "w") as f:
            f.write(browser.content())
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
        browser.locator("div").filter(
            has_text=re.compile(r"^GCP Monitoring alertConnect$")
        ).first.click()
        browser.get_by_role("button", name="Cancel").click()
        # connect resend provider
        browser.locator("div").filter(
            has_text=re.compile(r"^resend messagingConnect$")
        ).first.click()
        browser.get_by_placeholder("Enter provider name").click()
        random_provider_name = "".join(
            [random.choice(string.ascii_letters) for i in range(10)]
        )
        browser.get_by_placeholder("Enter provider name").fill(random_provider_name)
        browser.get_by_placeholder("Enter provider name").press("Tab")
        browser.get_by_placeholder("Enter api_key").fill("bla")
        browser.get_by_role("button", name="Connect").click()
        # wait a bit
        browser.wait_for_selector("text=Connected", timeout=15000)
        # make sure the provider is connected
        browser.get_by_text(f"resend id: {random_provider_name}").click()
    except Exception:
        # Current file + test name for unique html and png dump.
        current_test_name = \
            "playwright_dump_" + \
            os.path.basename(__file__)[:-3] + \
            "_" + sys._getframe().f_code.co_name

        browser.screenshot(path=current_test_name + ".png")
        with open(current_test_name + ".html", "w") as f:
            f.write(browser.content())
        raise
