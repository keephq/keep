from keep.providers.providers_factory import ProvidersFactory
import requests
from playwright.sync_api import expect


def trigger_alert(provider_name):
    provider = ProvidersFactory.get_provider_class(provider_name)
    requests.post(
        f"http://localhost:8080/alerts/event/{provider_name}",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": "really_random_secret",
        },
        json=provider.simulate_alert(),
    )

def open_connected_provider(browser, provider_type, provider_name):
    browser.locator(
        f"button:has-text('{provider_type}'):has-text('Connected'):has-text('{provider_name}')"
    ).click()

def install_webhook_provider(browser, provider_name, webhook_url, webhook_action):
    """
    Installs webhook provider, given that you are on the providers page.
    """
    browser.get_by_placeholder("Filter providers...").click()
    browser.get_by_placeholder("Filter providers...").clear()
    browser.get_by_placeholder("Filter providers...").fill("Webhook")
    browser.get_by_placeholder("Filter providers...").press("Enter")
    browser.get_by_text("Available Providers").hover()
    webhook_title = browser.locator(
        "button:has-text('Webhook'):not(:has-text('Connected')):not(:has-text('Linked'))"
    )
    webhook_title.first.hover()
    webhook_title.first.click()

    browser.get_by_placeholder("Enter provider name").fill(provider_name)
    browser.get_by_placeholder("Enter url").fill(webhook_url)
    browser.mouse.wheel(1000, 10000)
    browser.get_by_role("button", name="POST", exact=True).click()
    browser.get_by_role("option", name="GET", exact=True).click()

    browser.get_by_role("button", name="Connect", exact=True).click()
    browser.mouse.wheel(0, 0) # Scrolling back to initial position


def delete_provider(browser, provider_type, provider_name):
    """
    Deletes a Connected provider
    """
    open_connected_provider(browser=browser, provider_type=provider_type, provider_name=provider_name)
    browser.once("dialog", lambda dialog: dialog.accept())
    browser.get_by_role("button", name="Delete").click()


def assert_connected_provider_count(browser, provider_type, provider_name, provider_count):
    """
    Asserts the number of **Connected** providers
    """
    expect(
        browser.locator(
            f"button:has-text('{provider_type}'):has-text('Connected'):has-text('{provider_name}')"
        )
    ).to_have_count(provider_count)

def assert_scope_text_count(browser, contains_text, count):
    """
    Validates the count of scopes having text "contains text".
    To check for valid scopes, pass contains_text="Valid"
    """
    expect(
            browser.locator(f"span.tremor-Badge-text:has-text('{contains_text}')")
        ).to_have_count(count)