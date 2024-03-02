import os

from playwright.sync_api import Page, expect

KEEP_UI_URL = os.environ.get("KEEP_UI_URL", "http://localhost:3000")


def test_keep_sanity(page: Page, keep_service):
    # Your test code here. The `keep_service` is already up and running.
    page.goto(KEEP_UI_URL)
    expect(page).to_have_title("Sign In")


def test_keep_login(page: Page, keep_service):
    # Navigate to the login page
    page.goto(KEEP_UI_URL)

    # Wait for the username input to be visible
    page.wait_for_selector('input[name="username"]')

    # Fill in the username and password
    page.fill('input[name="username"]', "keep")
    page.fill('input[name="password"]', "keep")

    # Click the submit button
    with page.expect_navigation() as navigation_info:
        page.click('button[type="submit"]')

    # Get the response from the navigation
    assert navigation_info.value.status == 500
