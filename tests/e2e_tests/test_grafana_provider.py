import os
import sys
from datetime import datetime

import requests
from playwright.sync_api import expect

from tests.e2e_tests.utils import trigger_alert, assert_scope_text_count, open_connected_provider, delete_provider, assert_connected_provider_count


# NOTE 2: to run the tests with a browser, uncomment this:
# os.environ["PLAYWRIGHT_HEADLESS"] = "false"

GRAFANA_HOST = "http://grafana:3000"
GRAFANA_HOST_LOCAL = "http://localhost:3002"
KEEP_UI_URL = "http://localhost:3000"


def get_grafana_access_token(role: str):
    headers = {
        "Content-Type": "application/json",
    }
    json_data_service_account = {
        "name": f'test-{role}-{datetime.now().strftime("%Y%m%d%H%M%S")}',
        "role": role,
    }
    auth = ("admin", "admin")
    service_account = requests.post(
        f"{GRAFANA_HOST_LOCAL}/api/serviceaccounts",
        headers=headers,
        json=json_data_service_account,
        auth=auth,
    )
    service_account = service_account.json()

    json_data__token = {
        "name": f'test-token-{datetime.now().strftime("%Y%m%d%H%M%S")}',
    }

    token_response = requests.post(
        f'{GRAFANA_HOST_LOCAL}/api/serviceaccounts/{service_account["id"]}/tokens',
        headers=headers,
        json=json_data__token,
        auth=("admin", "admin"),
    )
    return token_response.json()["key"]


def open_grafana_card(browser):
    browser.get_by_placeholder("Filter providers...").click()
    browser.get_by_placeholder("Filter providers...").clear()
    browser.get_by_placeholder("Filter providers...").fill("Grafana")
    browser.get_by_placeholder("Filter providers...").press("Enter")
    browser.get_by_text("Available Providers").hover()
    grafana_tile = browser.locator(
        "button:has-text('Grafana'):not(:has-text('Connected')):not(:has-text('Linked'))"
    )
    grafana_tile.first.hover()
    grafana_tile.first.click()


def test_grafana_provider(browser):
    try:
        provider_name = "playwright_test_" + datetime.now().strftime("%Y%m%d%H%M%S")
        provider_name_invalid = provider_name + "-invalid"
        provider_name_readonly = provider_name + "-read-only"
        provider_name_success = provider_name + "-success"

        browser.goto(f"{KEEP_UI_URL}/signin")
        browser.get_by_role("link", name="Providers").hover()
        browser.get_by_role("link", name="Providers").click()

        browser.wait_for_timeout(10000)
        # First trying to install with invalid token, provider installation should fail
        open_grafana_card(browser)
        browser.get_by_placeholder("Enter provider name").fill(provider_name_invalid)
        browser.get_by_placeholder("Enter token").fill("random_token_UwU")
        browser.get_by_placeholder("Enter host").fill(GRAFANA_HOST)
        browser.get_by_role("button", name="Connect", exact=True).click()
        assert_scope_text_count(browser=browser, contains_text="Missing Scope", count=3)
        browser.get_by_role("button", name="Cancel", exact=True).click()

        # Then trying to install with read scope, webhook installation should fail
        open_grafana_card(browser)
        browser.get_by_placeholder("Enter provider name").fill(provider_name_readonly)
        browser.get_by_placeholder("Enter token").fill(
            get_grafana_access_token("Viewer")
        )
        browser.get_by_placeholder("Enter host").fill(GRAFANA_HOST)
        browser.get_by_role("button", name="Connect", exact=True).click()
        browser.wait_for_timeout(5000)
        # browser.reload()
        open_connected_provider(browser=browser, provider_type="Grafana", provider_name=provider_name_readonly)
        assert_scope_text_count(browser=browser, contains_text="Missing Scope", count=2)
        assert_scope_text_count(browser=browser, contains_text="Valid", count=1)
        browser.get_by_role("button", name="Cancel", exact=True).click()

        # Then trying to install with admin scope, webhook installation should pass
        open_grafana_card(browser)
        browser.get_by_placeholder("Enter provider name").fill(provider_name_success)
        browser.get_by_placeholder("Enter token").fill(
            get_grafana_access_token("Admin")
        )
        browser.get_by_placeholder("Enter host").fill(GRAFANA_HOST)
        browser.get_by_role("button", name="Connect", exact=True).click()
        open_connected_provider(browser=browser, provider_type="Grafana", provider_name=provider_name_success)
        toast_div = browser.locator("div.Toastify")
        browser.get_by_role("button", name="Install/Update Webhook", exact=True).click()
        expect(toast_div).to_contain_text("grafana webhook installed", timeout=10000)
        assert_scope_text_count(browser=browser, contains_text="Valid", count=3)
        browser.get_by_role("button", name="Cancel", exact=True).click()

        trigger_alert("grafana")
        browser.get_by_role("link", name="Feed").hover()
        browser.get_by_role("link", name="Feed").click()

        max_attemps = 5

        for attempt in range(max_attemps):
            print(f"Attempt {attempt + 1} to load alerts...")
            browser.get_by_role("link", name="Feed").click()

            try:
                # Wait for an element that indicates alerts have loaded
                try:
                    browser.wait_for_selector(
                        "text=HighMemoryConsumption", timeout=5000
                    )
                    print("Alerts loaded successfully.")
                    break
                except Exception:
                    browser.wait_for_selector("text=NetworkLatencyIsHigh", timeout=5000)
                    print("Alerts loaded successfully.")
                    break
            except Exception:
                if attempt < max_attemps - 1:
                    print("Alerts not loaded yet. Retrying...")
                    browser.reload()
                else:
                    print("Failed to load alerts after maximum attempts.")
                    raise Exception("Failed to load alerts after maximum attempts.")

        browser.get_by_role("link", name="Providers").hover()
        browser.get_by_role("link", name="Providers").click()
        providers_to_delete = [provider_name_readonly, provider_name_success]

        for provider_to_delete in providers_to_delete:
            # Perform actions on each matching element
            delete_provider(browser=browser, provider_type="Grafana", provider_name=provider_to_delete)
            # Assert provider was deleted
            assert_connected_provider_count(browser=browser, provider_type="Grafana", provider_name=provider_to_delete, provider_count=0)

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
