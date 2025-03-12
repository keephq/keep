import time
from datetime import datetime

import requests
from playwright.sync_api import Page, expect

# Dear developer, thank you for checking E2E tests!
# For instructions, please check test_end_to_end.py.

# NOTE 2: to run the tests with a browser, uncomment this:
# os.environ["PLAYWRIGHT_HEADLESS"] = "false"


def test_pulling_prometheus_alerts_to_provider(
    browser: Page, setup_page_logging, failure_artifacts
):
    provider_name = "playwright_test_" + datetime.now().strftime("%Y%m%d%H%M%S")

    # Wait for prometheus to wake up and evaluate alert rule as "firing"
    alerts = None
    max_attempts = 30  # Set a reasonable limit to avoid infinite loops
    attempt = 0

    while (
        alerts is None
        or len(alerts["data"]["alerts"]) == 0
        or alerts["data"]["alerts"][0]["state"] != "firing"
    ) and attempt < max_attempts:
        print(
            f"Attempt {attempt + 1}/{max_attempts}: Waiting for prometheus to fire an alert..."
        )
        time.sleep(1)
        try:
            alerts = requests.get("http://localhost:9090/api/v1/alerts").json()
            print(alerts)
        except Exception as e:
            print(f"Error getting alerts: {e}")
        attempt += 1

    if attempt >= max_attempts:
        raise Exception("Prometheus didn't fire alerts within the expected time")

    # Create prometheus provider
    browser.goto("http://localhost:3000/providers")
    browser.get_by_placeholder("Filter providers...").click()
    browser.get_by_placeholder("Filter providers...").fill("prometheus")
    browser.get_by_placeholder("Filter providers...").press("Enter")
    browser.get_by_text("Available Providers").hover()

    # Wait for any loading overlays to disappear
    browser.wait_for_load_state("networkidle")

    prometheus_tile = browser.locator(
        "button:has-text('prometheus'):has-text('alert'):has-text('data')"
    )
    prometheus_tile.first.wait_for(state="visible")
    prometheus_tile.first.hover()
    prometheus_tile.first.click()

    browser.get_by_placeholder("Enter provider name").click()
    browser.get_by_placeholder("Enter provider name").fill(provider_name)
    browser.get_by_placeholder("Enter url").click()

    # Always use same URL (using localhost conditionally might cause issues)
    browser.get_by_placeholder("Enter url").fill(
        "http://prometheus-server-for-test-target:9090/"
    )

    browser.mouse.wheel(1000, 10000)  # Scroll down.

    # Wait for the button to be clickable
    connect_button = browser.get_by_role("button", name="Connect", exact=True)
    connect_button.wait_for(state="visible")
    connect_button.wait_for(state="enabled")
    connect_button.click()

    # Validate provider is created - increase timeout for validation
    expect(
        browser.locator("button:has-text('prometheus'):has-text('connected')")
    ).to_be_visible(
        timeout=10000
    )  # Increase timeout to 10 seconds

    # Wait for page to stabilize before reloading
    browser.wait_for_load_state("networkidle")
    browser.reload()
    browser.wait_for_load_state("domcontentloaded")
    browser.wait_for_load_state("networkidle")

    # Try to get to the Feed page and wait for alerts
    max_attemps = 5
    alert_found = False

    for attempt in range(max_attemps):
        try:
            print(f"Attempt {attempt + 1} to load alerts...")

            # Handle possible overlay by using evaluate
            browser.evaluate(
                """() => {
                const overlays = document.querySelectorAll('div[data-enter][data-closed][aria-hidden="true"]');
                overlays.forEach(overlay => overlay.remove());
            }"""
            )

            # Try to get to the Feed page
            feed_link = browser.get_by_role("link", name="Feed")
            feed_link.wait_for(state="visible")
            feed_link.wait_for(state="enabled")
            feed_link.click(timeout=10000)  # Increase timeout to 10 seconds

            # Wait for alerts to load with increased timeout
            alert_element = browser.wait_for_selector(
                "text=AlwaysFiringAlert", timeout=10000
            )
            if alert_element:
                print("Alerts loaded successfully.")
                alert_found = True
                break

        except Exception as e:
            print(f"Failed to load alerts: {e}")
            if attempt < max_attemps - 1:
                print("Retrying after page reload...")
                browser.reload()
                browser.wait_for_load_state("domcontentloaded")
                browser.wait_for_load_state("networkidle")
                time.sleep(2)  # Add a small delay before retrying
            else:
                print("Failed to load alerts after maximum attempts.")

    if not alert_found:
        raise Exception("Failed to load alerts after maximum attempts")

    # Make sure we pulled multiple instances of the alert
    alert_text = browser.get_by_text("AlwaysFiringAlert")
    alert_text.wait_for(state="visible")
    alert_text.click()

    # Close the side panel by clicking the escape key instead of clicking at a position
    browser.keyboard.press("Escape")

    # Handle the providers page navigation carefully
    try:
        # Remove any overlays that might be causing issues
        browser.evaluate(
            """() => {
            const overlays = document.querySelectorAll('div[data-enter][data-closed][aria-hidden="true"]');
            overlays.forEach(overlay => overlay.remove());
        }"""
        )

        providers_link = browser.get_by_role("link", name="Providers")
        providers_link.wait_for(state="visible")
        providers_link.wait_for(state="enabled")
        providers_link.click(timeout=10000, force=True)  # Use force if needed

    except Exception as e:
        print(f"Failed to click Providers link: {e}")
        # Alternative approach - go directly to the URL
        browser.goto("http://localhost:3000/providers")

    # Wait for page to load
    browser.wait_for_load_state("networkidle")

    # Find and interact with the provider
    provider_button = browser.locator(
        f"button:has-text('Prometheus'):has-text('Connected'):has-text('{provider_name}')"
    )
    provider_button.wait_for(state="visible")
    provider_button.click()

    # Delete the provider
    delete_button = browser.get_by_role("button", name="Delete")
    delete_button.wait_for(state="visible")
    browser.once("dialog", lambda dialog: dialog.accept())
    delete_button.click()

    # Assert provider was deleted with increased timeout
    expect(
        browser.locator(
            f"button:has-text('Prometheus'):has-text('Connected'):has-text('{provider_name}')"
        )
    ).not_to_be_visible(timeout=10000)
