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
import re
import string
import sys

# Running the tests in GitHub Actions:
# - Look at the test-pr-e2e.yml file in the .github/workflows directory.


# os.environ["PLAYWRIGHT_HEADLESS"] = "false"


def test_sanity(browser):
    try:
        browser.goto("http://localhost:3000/")
        browser.wait_for_url("http://localhost:3000/incidents")
        assert "Keep" in browser.title()
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
