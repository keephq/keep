import json
import os
import sys

import requests
from playwright.sync_api import Page, expect

from keep.providers.providers_factory import ProvidersFactory

KEEP_UI_URL = "http://localhost:3000"


def trigger_alert(provider_name):
    provider = ProvidersFactory.get_provider_class(provider_name)
    token = get_token()
    requests.post(
        f"http://localhost:8080/alerts/event/{provider_name}",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + token,
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
    browser.locator("li:has-text('GET')").click()

    browser.get_by_role("button", name="Connect", exact=True).click()
    browser.mouse.wheel(0, 0)  # Scrolling back to initial position


def delete_provider(browser, provider_type, provider_name):
    """
    Deletes a Connected provider
    """
    open_connected_provider(
        browser=browser, provider_type=provider_type, provider_name=provider_name
    )
    browser.once("dialog", lambda dialog: dialog.accept())
    browser.get_by_role("button", name="Delete").click()


def assert_connected_provider_count(
    browser, provider_type, provider_name, provider_count
):
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


def init_e2e_test(browser: Page, tenant_id: str = None, next_url="/", wait_time=0):
    # Store all requests for debugging
    page = browser if hasattr(browser, "goto") else browser.page
    requests_log = []

    def log_request(request):
        requests_log.append(
            {
                "url": request.url,
                "method": request.method,
                "time": request.timing,
                "status": None,  # Will be updated in response handler
                "pending": True,
            }
        )

    def log_response(response):
        # Find the matching request and update it
        request_url = response.request.url
        for req in requests_log:
            if req["url"] == request_url and req["pending"]:
                req["status"] = response.status
                req["pending"] = False
                break

    def log_request_failed(request):
        # Mark the request as failed
        for req in requests_log:
            if req["url"] == request.url and req["pending"]:
                req["status"] = "FAILED"
                req["pending"] = False
                break

    # Add event listeners to track requests
    page.on("request", log_request)
    page.on("response", log_response)
    page.on("requestfailed", log_request_failed)

    if not tenant_id:
        tenant_id = "keep" + str(os.getpid())

    url = f"{KEEP_UI_URL}{next_url}?tenantId={tenant_id}"
    print("Going to URL: ", url)
    try:
        page.goto(url, timeout=15000)
        if wait_time:
            page.wait_for_timeout(wait_time)

    except Exception as e:
        print(f"Navigation failed: {e}")

        # Print all requests that are still pending
        pending_requests = [req for req in requests_log if req["pending"]]
        if pending_requests:
            print(f"\n==== PENDING REQUESTS ({len(pending_requests)}) ====")
            for req in pending_requests:
                print(f"  {req['method']} {req['url']}")

        # Print all requests, sorted by time to complete or status
        print(f"\n==== ALL REQUESTS ({len(requests_log)}) ====")
        # Sort by URL for better readability
        for req in sorted(requests_log, key=lambda r: r["url"]):
            status = req["status"] or "PENDING"
            print(f"  {req['method']} {status} {req['url']}")

        # Check for slow requests (taking more than 5 seconds)
        slow_requests = []
        for req in requests_log:
            if (
                not req["pending"]
                and req["time"]
                and req["time"].get("responseEnd", 0)
                - req["time"].get("requestStart", 0)
                > 5000
            ):
                slow_requests.append(req)

        if slow_requests:
            print(f"\n==== SLOW REQUESTS ({len(slow_requests)}) ====")
            for req in sorted(
                slow_requests,
                key=lambda r: (
                    r["time"].get("responseEnd", 0) - r["time"].get("requestStart", 0)
                ),
                reverse=True,
            ):
                duration = (
                    req["time"].get("responseEnd", 0)
                    - req["time"].get("requestStart", 0)
                ) / 1000
                print(
                    f"  {req['method']} {req['status']} {req['url']} - {duration:.2f}s"
                )

        # dump to file
        current_test_name = get_current_test_name()
        with open(f"requests_{current_test_name}.log", "w") as f:
            f.write(json.dumps(requests_log, indent=2))
    finally:
        # Remove event listeners
        page.remove_listener("request", log_request)
        page.remove_listener("response", log_response)
        page.remove_listener("requestfailed", log_request_failed)

    # take a screenshot because why not
    try:
        take_screenshot(browser)
    except Exception as e:
        print("Error taking screenshot: ", e)
        pass


def take_screenshot(page):
    """Save screenshots, HTML content, and console logs on test failure."""
    # Generate unique name for the dump files
    current_test_name = "screenshot_"

    # try to get test_name from PYTEST_CURRENT_TEST
    test_name = os.getenv("PYTEST_CURRENT_TEST") or "screenshot"
    # Replace invalid filename characters with underscores
    invalid_chars = [
        ":",
        "/",
        "\\",
        "?",
        "*",
        '"',
        "<",
        ">",
        "|",
        " ",
        "[",
        "]",
        "(",
        ")",
        "'",
    ]
    for char in invalid_chars:
        test_name = test_name.replace(char, "_")

    current_test_name += test_name

    # Save screenshot
    page.screenshot(path=current_test_name + ".png")


def get_token():
    pid = os.getpid()
    return json.dumps(
        {
            "tenant_id": "keep" + str(pid),
            "user_id": "keep-user-for-no-auth-purposes",
        }
    )


# Generate unique name for the dump files
def get_current_test_name():
    current_test_name = "playwright_dump_" + os.path.basename(__file__)[:-3] + "_"

    # try to get test_name from PYTEST_CURRENT_TEST
    test_name = os.getenv("PYTEST_CURRENT_TEST")

    if test_name:
        # Replace invalid filename characters with underscores
        invalid_chars = [
            ":",
            "/",
            "\\",
            "?",
            "*",
            '"',
            "<",
            ">",
            "|",
            " ",
            "[",
            "]",
            "(",
            ")",
            "'",
        ]
        for char in invalid_chars:
            test_name = test_name.replace(char, "_")
        print(f"test_name: {test_name}")
        current_test_name += test_name
    else:
        # this should never happen
        print("THIS SHOULD NEVER HAPPEN")
        current_test_name += sys._getframe().f_code.co_name
    return current_test_name
