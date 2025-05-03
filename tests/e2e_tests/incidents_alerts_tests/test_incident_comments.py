import time
from datetime import datetime

from playwright.sync_api import Page, expect

from tests.e2e_tests.incidents_alerts_tests.incidents_alerts_setup import (
    KEEP_UI_URL,
    KEEP_API_URL,
)
from tests.e2e_tests.test_end_to_end import init_e2e_test, setup_console_listener
from tests.e2e_tests.utils import get_token


def test_incident_comment_with_mentions(browser: Page):
    """Test adding comments with user mentions to incidents."""
    log_entries = []
    setup_console_listener(browser, log_entries)

    # Initialize test and navigate to incidents page
    init_e2e_test(browser, next_url="/incidents")

    # Create a test incident first
    browser.locator("[data-testid='create-incident-button']").click()
    browser.locator("[data-testid='incident-name-input']").fill("Test Incident for Comments")
    browser.locator("[data-testid='incident-summary-input']").fill("Testing comment functionality with user mentions")
    browser.locator("[data-testid='create-incident-submit']").click()

    # Wait for incident to be created and navigate to its details
    browser.wait_for_selector("table[data-testid='incidents-table'] tbody tr", timeout=5000)
    browser.locator("table[data-testid='incidents-table'] tbody tr").first.click()

    # Add a comment with user mentions
    browser.locator("[data-testid='add-comment-button']").click()
    comment_input = browser.locator("[data-testid='comment-input']")
    comment_input.fill("Hey @Rohit.dash and @Oz.rooh, please take a look at this incident")

    # Verify mention suggestions appear
    browser.wait_for_selector("[data-testid='mention-suggestions']")
    expect(browser.locator("[data-testid='mention-suggestions']")).to_be_visible()

    # Submit the comment
    browser.locator("[data-testid='submit-comment-button']").click()

    # Verify the comment appears with proper mention formatting
    comment_element = browser.locator("[data-testid='incident-comment']").first
    expect(comment_element).to_contain_text("@rohit.dash")
    expect(comment_element).to_contain_text("@oz.rooh")

    # Verify mentioned users are highlighted
    mentioned_users = browser.locator("[data-testid='mentioned-user']")
    expect(mentioned_users).to_have_count(2)
    expect(mentioned_users.first).to_have_class("mentioned-user")

    # Test editing a comment with mentions
    browser.locator("[data-testid='edit-comment-button']").first.click()
    edit_input = browser.locator("[data-testid='edit-comment-input']")
    edit_input.fill("Updated: @rohit.dash please check this ASAP")
    browser.locator("[data-testid='save-comment-button']").click()

    # Verify the edited comment
    updated_comment = browser.locator("[data-testid='incident-comment']").first
    expect(updated_comment).to_contain_text("Updated:")
    expect(updated_comment).to_contain_text("@rohit.dash")
    expect(updated_comment).not_to_contain_text("@oz.rooh")

    # Test comment with status change
    browser.locator("[data-testid='add-comment-button']").click()
    comment_input = browser.locator("[data-testid='comment-input']")
    comment_input.fill("@oz.rooh I'm acknowledging this incident")
    browser.locator("[data-testid='comment-status-select']").select_option("acknowledged")
    browser.locator("[data-testid='submit-comment-button']").click()

    # Verify status change comment
    status_comment = browser.locator("[data-testid='incident-comment']").first
    expect(status_comment).to_contain_text("acknowledged")
    expect(status_comment).to_contain_text("@oz.rooh")

    # Verify incident status updated
    expect(browser.locator("[data-testid='incident-status']")).to_have_text("acknowledged")