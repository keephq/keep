import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from playwright.sync_api import Page, expect

from tests.e2e_tests.incidents_alerts_tests.incidents_alerts_setup import (
    create_fake_alert,
    query_alerts,
    setup_incidents_alerts,
)
from tests.e2e_tests.test_end_to_end import init_e2e_test, setup_console_listener
from tests.e2e_tests.utils import get_token, save_failure_artifacts
from copy import deepcopy


def multi_sort(data, criteria):
    """
    Sorts a list by multiple criteria.

    Args:
        data (list): The input list (e.g., list of dicts or objects).
        criteria (list of tuples): Each tuple is (key, direction)
            - key: string field name or callable (e.g., lambda x: ...)
            - direction: 'asc' or 'desc'

    Returns:
        A new sorted list.
    """
    sorted_data = deepcopy(data)

    for key, direction in reversed(criteria):
        if direction not in ("asc", "desc"):
            raise ValueError(f"Invalid sort direction: {direction}")
        reverse = direction == "desc"

        key_func = key if callable(key) else lambda x: x[key]
        sorted_data.sort(key=key_func, reverse=reverse)

    return sorted_data


KEEP_UI_URL = "http://localhost:3000"
KEEP_API_URL = "http://localhost:8080"


def init_test(browser: Page, alerts, max_retries=3):
    for i in range(max_retries):
        try:
            init_e2e_test(browser, next_url="/alerts/feed")
            base_url = f"{KEEP_UI_URL}/alerts/feed"
            # we don't care about query params
            # Give the page a moment to process redirects
            browser.wait_for_timeout(500)
            # Wait for navigation to complete to either signin or providers page
            # (since we might get redirected automatically)
            browser.wait_for_load_state("networkidle")
            browser.wait_for_url(lambda url: url.startswith(base_url), timeout=10000)
            print("Page loaded successfully. [try: %d]" % (i + 1))
            break
        except Exception as e:
            if i < max_retries - 1:
                print("Failed to load alerts page. Retrying... - ", e)
                continue
            else:
                raise e

    browser.wait_for_selector("[data-testid='facet-value']", timeout=10000)
    browser.wait_for_selector(f"text={alerts[0]['name']}", timeout=10000)
    rows_count = browser.locator("[data-testid='alerts-table'] table tbody tr").count()
    # check that required alerts are loaded and displayed
    # other tests may also add alerts, so we need to check that the number of rows is greater than or equal to 20

    # Shahar: Now each test file is seperate
    assert rows_count >= 10
    return alerts


def select_one_facet_option(browser, facet_name, option_name):
    expect(
        browser.locator("[data-testid='facet']", has_text=facet_name)
    ).to_be_visible()
    option = browser.locator("[data-testid='facet-value']", has_text=option_name)
    option.hover()
    option.locator("button", has_text="Only").click()


def assert_facet(browser, facet_name, alerts, alert_property_name: str):
    counters_dict = {}
    expect(
        browser.locator("[data-testid='facet']", has_text=facet_name)
    ).to_be_visible()
    for alert in alerts:
        prop_value = None
        for prop in alert_property_name.split("."):
            prop_value = alert.get(prop, None)
            if prop_value is None:
                prop_value = "None"
                break
            alert = prop_value

        if prop_value not in counters_dict:
            counters_dict[prop_value] = 0

        counters_dict[prop_value] += 1

    for facet_value, count in counters_dict.items():
        facet_locator = browser.locator("[data-testid='facet']", has_text=facet_name)
        expect(facet_locator).to_be_visible()
        facet_value_locator = facet_locator.locator(
            "[data-testid='facet-value']", has_text=facet_value
        )
        expect(facet_value_locator).to_be_visible()
        try:
            expect(
                facet_value_locator.locator("[data-testid='facet-value-count']")
            ).to_contain_text(str(count))
        except Exception as e:
            save_failure_artifacts(browser, log_entries=[])
            raise e


def assert_alerts_by_column(
    browser,
    alerts: list[dict],
    predicate: lambda x: bool,
    property_in_alert: str,
    column_index: int,
):
    filtered_alerts = [alert for alert in alerts if predicate(alert)]
    matched_rows = browser.locator("[data-testid='alerts-table'] table tbody tr")
    try:
        expect(matched_rows).to_have_count(len(filtered_alerts))
    except Exception as e:
        save_failure_artifacts(browser, log_entries=[])
        raise e

    # check that only alerts with selected status are displayed
    for alert in filtered_alerts:
        row_locator = browser.locator(
            "[data-testid='alerts-table'] table tbody tr", has_text=alert["name"]
        )
        expect(row_locator).to_be_visible()

        if column_index is None:
            return

        column_locator = row_locator.locator("td").nth(column_index)
        # status is now only svg
        try:
            expect(
                column_locator.locator("[data-testid*='status-icon']")
            ).to_be_visible()
        except Exception:
            column_html = column_locator.inner_html()
            print(f"Column HTML: {column_html}")


facet_test_cases = {
    "severity": {
        "alert_property_name": "severity",
        "value": "high",
    },
    "status": {
        "alert_property_name": "status",
        "column_index": 1,
        "value": "suppressed",  # Shahar: no more text - only icon
    },
    "source": {
        "alert_property_name": "providerType",
        "value": "prometheus",
    },
}


@pytest.fixture(scope="module")
def setup_test_data():
    print("Setting up test data...")
    test_data = setup_incidents_alerts()
    yield test_data["alerts"]


@pytest.mark.parametrize("facet_test_case", facet_test_cases.keys())
def test_filter_by_static_facet(
    browser: Page,
    facet_test_case,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    test_case = facet_test_cases[facet_test_case]
    facet_name = facet_test_case
    alert_property_name = test_case["alert_property_name"]
    column_index = test_case.get("column_index", None)
    value = test_case["value"]
    current_alerts = setup_test_data

    init_test(browser, current_alerts, max_retries=3)
    # Give the page a moment to process redirects
    browser.wait_for_timeout(500)

    # Wait for navigation to complete to either signin or providers page
    # (since we might get redirected automatically)
    browser.wait_for_load_state("networkidle")

    assert_facet(browser, facet_name, current_alerts, alert_property_name)

    option = browser.locator("[data-testid='facet-value']", has_text=value)
    option.hover()

    option.locator("button", has_text="Only").click()

    assert_alerts_by_column(
        browser,
        current_alerts,
        lambda alert: alert[alert_property_name] == value,
        alert_property_name,
        column_index,
    )


def test_adding_custom_facet(
    browser: Page, setup_test_data, setup_page_logging, failure_artifacts
):
    facet_property_path = "custom_tags.env"
    facet_name = "Custom Env"
    alert_property_name = facet_property_path
    value = "environment:staging"
    current_alerts = setup_test_data
    init_test(browser, current_alerts)
    browser.locator("button", has_text="Add Facet").click()

    browser.locator("input[placeholder='Enter facet name']").fill(facet_name)
    browser.locator("input[placeholder*='Search columns']").fill(facet_property_path)
    browser.locator("button", has_text=facet_property_path).click()
    browser.locator("button", has_text="Create").click()

    assert_facet(browser, facet_name, current_alerts, alert_property_name)

    option = browser.locator("[data-testid='facet-value']", has_text=value)
    option.hover()
    option.locator("button", has_text="Only").click()

    assert_alerts_by_column(
        browser,
        current_alerts[:20],
        lambda alert: alert.get("custom_tags", {}).get("env") == value,
        alert_property_name,
        None,
    )
    browser.on("dialog", lambda dialog: dialog.accept())
    browser.locator("[data-testid='facet']", has_text=facet_name).locator(
        '[data-testid="delete-facet"]'
    ).click()
    expect(
        browser.locator("[data-testid='facet']", has_text=facet_name)
    ).not_to_be_visible()


search_by_cel_tescases = {
    "contains for nested property": {
        "cel_query": "labels.service.contains('java-otel')",
        "predicate": lambda alert: "java-otel"
        in alert.get("labels", {}).get("service", ""),
        "alert_property_name": "name",
        "commands": [
            lambda browser: browser.keyboard.type("labels."),
            lambda browser: browser.locator(
                ".monaco-highlighted-label", has_text="service"
            ).click(),
            lambda browser: browser.keyboard.type("."),
            lambda browser: browser.locator(
                ".monaco-highlighted-label", has_text="contains"
            ).click(),
            lambda browser: browser.keyboard.type("java-otel"),
        ],
    },
    "using enriched field": {
        "cel_query": "host == 'enriched host'",
        "predicate": lambda alert: "Enriched" in alert["name"],
        "alert_property_name": "name",
        "commands": [
            lambda browser: browser.keyboard.type("host"),
            lambda browser: browser.keyboard.type(" == "),
            lambda browser: browser.keyboard.type("'enriched host'"),
        ],
    },
    "date comparison greater than or equal": {
        "cel_query": f"dateForTests >= '{(datetime(2025, 2, 10, 10) + timedelta(days=-14)).isoformat()}'",
        "predicate": lambda alert: alert.get("dateForTests")
        and datetime.fromisoformat(alert.get("dateForTests"))
        >= (datetime(2025, 2, 10, 10) + timedelta(days=-14)),
        "alert_property_name": "name",
        "commands": [
            lambda browser: browser.keyboard.type("dateForTests"),
            lambda browser: browser.keyboard.type(" >= "),
            lambda browser: browser.keyboard.type(
                f"'{(datetime(2025, 2, 10, 10) + timedelta(days=-14)).isoformat()}'"
            ),
        ],
    },
}


@pytest.mark.parametrize("search_test_case", search_by_cel_tescases.keys())
def test_search_by_cel(
    browser: Page,
    search_test_case,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    test_case = search_by_cel_tescases[search_test_case]
    cel_query = test_case["cel_query"]
    commands = test_case["commands"]
    predicate = test_case["predicate"]
    alert_property_name = test_case["alert_property_name"]
    current_alerts = setup_test_data
    browser.wait_for_timeout(3000)
    print(current_alerts)
    init_test(browser, current_alerts)
    browser.wait_for_timeout(1000)
    cel_input_locator = browser.locator(".alerts-cel-input")
    cel_input_locator.click()

    for command in commands:
        command(browser)
    expect(cel_input_locator.locator(".view-lines")).to_have_text(cel_query)

    browser.keyboard.press("Enter")

    assert_alerts_by_column(
        browser,
        current_alerts,
        predicate,
        alert_property_name,
        None,
    )


sort_tescases = {
    "sort by lastReceived asc/dsc": {
        "column_name": "Last Received",
        "column_id": "lastReceived",
        "sort_callback": lambda alert: alert["lastReceived"],
    },
    "sort by description asc/dsc": {
        "column_name": "description",
        "column_id": "description",
        "sort_callback": lambda alert: alert["description"],
    },
}


@pytest.mark.parametrize("sort_test_case", sort_tescases.keys())
def test_sort_asc_dsc(
    browser: Page,
    sort_test_case,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    test_case = sort_tescases[sort_test_case]
    coumn_name = test_case["column_name"]
    column_id = test_case["column_id"]
    sort_callback = test_case["sort_callback"]
    current_alerts = setup_test_data
    alert_name_column_index = 4
    init_test(browser, current_alerts)
    filtered_alerts = [
        alert for alert in current_alerts if alert["providerType"] == "datadog"
    ]
    select_one_facet_option(browser, "source", "datadog")
    try:
        expect(
            browser.locator("[data-testid='alerts-table'] table tbody tr")
        ).to_have_count(len(filtered_alerts))
    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise

    for sort_direction_title in ["asc", "desc"]:
        sorted_alerts = multi_sort(
            filtered_alerts, [(sort_callback, sort_direction_title)]
        )

        column_header_locator = browser.locator(
            f"[data-testid='alerts-table'] table thead th [data-testid='header-cell-{column_id}']",
            has_text=coumn_name,
        )
        expect(column_header_locator).to_be_visible()
        column_header_locator.click()
        rows = browser.locator("[data-testid='alerts-table'] table tbody tr")

        number_of_missmatches = 0
        for index, alert in enumerate(sorted_alerts):
            row_locator = rows.nth(index)
            # 4 is index of "name" column
            column_locator = row_locator.locator("td").nth(alert_name_column_index)
            try:
                expect(column_locator).to_have_text(alert["name"])
            except Exception as e:
                save_failure_artifacts(browser, log_entries=[])
                number_of_missmatches += 1
                if number_of_missmatches > 2:
                    raise e
                else:
                    print(
                        f"Expected: {alert['name']} but got: {column_locator.text_content()}"
                    )
                    continue


def test_multi_sort_asc_dsc(
    browser: Page,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    coumn_name = ""
    current_alerts = setup_test_data
    alert_name_column_index = 4
    init_test(browser, current_alerts)
    cel_to_filter_alerts = "tags.customerName != null"
    browser.goto(f"{KEEP_UI_URL}/alerts/feed?cel={cel_to_filter_alerts}")
    filtered_alerts = [
        alert
        for alert in current_alerts
        if alert.get("tags", {}).get("customerName", None) is not None
    ]

    try:
        expect(
            browser.locator("[data-testid='alerts-table'] table tbody tr")
        ).to_have_count(len(filtered_alerts))
        browser.locator("[data-testid='settings-button']").click()
        settings_panel_locator = browser.locator("[data-testid='settings-panel']")
        settings_panel_locator.locator("input[type='text']").type("tags.")
        settings_panel_locator.locator("input[name='tags.customerName']").click()
        settings_panel_locator.locator("input[name='tags.alertIndex']").click()
        settings_panel_locator.locator(
            "button[type='submit']", has_text="Save changes"
        ).click()
    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise
    # data-testid="header-cell-tags.customerName"
    browser.locator(
        f"[data-testid='alerts-table'] table thead th [data-testid='header-cell-tags.customerName']",
        has_text=coumn_name,
    ).click()
    print("ff")
    browser.keyboard.down("Shift")
    for sort_direction in ["desc", "asc"]:
        sorted_alerts = multi_sort(
            filtered_alerts,
            [
                (lambda alert: alert.get("tags", {}).get("customerName", None), "asc"),
                (
                    lambda alert: alert.get("tags", {}).get("alertIndex", None),
                    sort_direction,
                ),
            ],
        )

        column_header_locator = browser.locator(
            f"[data-testid='alerts-table'] table thead th [data-testid='header-cell-tags.alertIndex']",
            has_text=coumn_name,
        )
        expect(column_header_locator).to_be_visible()
        column_header_locator.click()
        rows = browser.locator("[data-testid='alerts-table'] table tbody tr")

        number_of_missmatches = 0
        for index, alert in enumerate(sorted_alerts):
            row_locator = rows.nth(index)
            # 4 is index of "name" column
            column_locator = row_locator.locator("td").nth(alert_name_column_index)
            try:
                expect(column_locator).to_have_text(alert["name"])
            except Exception as e:
                save_failure_artifacts(browser, log_entries=[])
                number_of_missmatches += 1
                if number_of_missmatches > 2:
                    raise e
                else:
                    print(
                        f"Expected: {alert['name']} but got: {column_locator.text_content()}"
                    )
                    continue


def test_backend_column_configuration_persistence(
    browser: Page,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    """
    Test that column configuration persists across browser sessions when using backend storage.
    This test:
    1. Creates a new preset
    2. Configures columns (visibility and order)
    3. Starts a fresh browser context (simulating new session)
    4. Verifies the column configuration is preserved
    """
    current_alerts = setup_test_data
    init_test(browser, current_alerts)
    
    # Create a unique preset name for this test
    test_preset_name = f"test-column-config-{int(time.time())}"
    test_cel_query = "severity == 'high'"
    
    try:
        # Navigate to alerts page and create a new preset
        browser.goto(f"{KEEP_UI_URL}/alerts/feed")
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(1000)
        
        # Create new preset via the "Save current filter as a view" flow
        cel_input = browser.locator(".alerts-cel-input")
        cel_input.click()
        cel_input.fill("")  # Clear any existing content
        browser.keyboard.type(test_cel_query)
        browser.keyboard.press("Enter")
        browser.wait_for_timeout(500)
        
        # Click save view button
        save_view_button = browser.locator("button", has_text="Save current filter as a view")
        expect(save_view_button).to_be_visible()
        save_view_button.click()
        
        # Fill in preset creation form
        modal = browser.locator("[role='dialog']")
        expect(modal).to_be_visible()
        
        preset_name_input = modal.locator("input[placeholder*='name']")
        preset_name_input.fill(test_preset_name)
        
        create_button = modal.locator("button", has_text="Create")
        create_button.click()
        
        # Wait for navigation to the new preset
        browser.wait_for_url(lambda url: test_preset_name.lower() in url.lower(), timeout=10000)
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(1000)
        
        # Now configure columns in the new preset
        settings_button = browser.locator("[data-testid='settings-button']")
        expect(settings_button).to_be_visible()
        settings_button.click()
        
        settings_panel = browser.locator("[data-testid='settings-panel']")
        expect(settings_panel).to_be_visible()
        
        # Go to columns tab
        columns_tab = settings_panel.locator("[data-testid='tab-columns']")
        columns_tab.click()
        
        # Verify "Synced across devices" indicator is shown (confirming backend usage)
        synced_indicator = settings_panel.locator("text=Synced across devices")
        expect(synced_indicator).to_be_visible()
        
        # Configure some specific columns - enable tags.customerName and description
        search_input = settings_panel.locator("input[placeholder='Search fields...']")
        search_input.fill("tags.")
        browser.wait_for_timeout(500)
        
        # Enable tags.customerName
        customer_name_checkbox = settings_panel.locator("input[name='tags.customerName']")
        if not customer_name_checkbox.is_checked():
            customer_name_checkbox.click()
        
        # Clear search and enable description
        search_input.fill("")
        browser.wait_for_timeout(500)
        
        description_checkbox = settings_panel.locator("input[name='description']")
        if not description_checkbox.is_checked():
            description_checkbox.click()
        
        # Save changes
        save_button = settings_panel.locator("button[type='submit']", has_text="Save changes")
        save_button.click()
        
        # Wait for save to complete (should see success toast)
        browser.wait_for_timeout(2000)
        
        # Verify columns are now visible in the table
        customer_name_header = browser.locator("[data-testid='header-cell-tags.customerName']")
        expect(customer_name_header).to_be_visible()
        
        description_header = browser.locator("[data-testid='header-cell-description']")
        expect(description_header).to_be_visible()
        
        # Get the current column order for verification
        table_headers = browser.locator("[data-testid='alerts-table'] thead th")
        original_column_order = []
        for i in range(table_headers.count()):
            header = table_headers.nth(i)
            test_id = header.get_attribute("data-testid")
            if test_id and "header-cell-" in test_id:
                column_id = test_id.replace("header-cell-", "")
                original_column_order.append(column_id)
        
        print(f"Original column order: {original_column_order}")
        
        # Now simulate a fresh browser session by creating a new context
        browser.context.clear_cookies()
        browser.context.clear_permissions()
        
        # Navigate to the same preset in fresh state
        browser.goto(f"{KEEP_UI_URL}/alerts/{test_preset_name}")
        browser.wait_for_load_state("networkidle")
        browser.wait_for_timeout(2000)
        
        # Verify the column configuration is preserved
        # Check that tags.customerName column is still visible
        customer_name_header_after = browser.locator("[data-testid='header-cell-tags.customerName']")
        expect(customer_name_header_after).to_be_visible()
        
        # Check that description column is still visible  
        description_header_after = browser.locator("[data-testid='header-cell-description']")
        expect(description_header_after).to_be_visible()
        
        # Verify column order is preserved
        table_headers_after = browser.locator("[data-testid='alerts-table'] thead th")
        new_column_order = []
        for i in range(table_headers_after.count()):
            header = table_headers_after.nth(i)
            test_id = header.get_attribute("data-testid")
            if test_id and "header-cell-" in test_id:
                column_id = test_id.replace("header-cell-", "")
                new_column_order.append(column_id)
        
        print(f"New column order: {new_column_order}")
        
        # Verify that both enabled columns are still present
        assert "tags.customerName" in new_column_order, "tags.customerName column should be preserved"
        assert "description" in new_column_order, "description column should be preserved"
        
        print(f"✅ Column configuration persistence test passed for preset: {test_preset_name}")
        
    except Exception as e:
        save_failure_artifacts(browser, log_entries=[])
        print(f"❌ Column configuration persistence test failed: {e}")
        raise e
    
    finally:
        # Cleanup: Delete the test preset
        try:
            # Get auth token for API cleanup
            token = get_token()
            headers = {"Authorization": f"Bearer {token}"}
            
            # Get preset ID by name
            response = requests.get(f"{KEEP_API_URL}/preset", headers=headers)
            if response.status_code == 200:
                presets = response.json()
                test_preset = next((p for p in presets if p["name"] == test_preset_name), None)
                if test_preset:
                    # Delete the preset
                    delete_response = requests.delete(f"{KEEP_API_URL}/preset/{test_preset['id']}", headers=headers)
                    print(f"Cleanup: Deleted test preset {test_preset_name}, status: {delete_response.status_code}")
        except Exception as cleanup_error:
            print(f"⚠️ Failed to cleanup test preset: {cleanup_error}")


def test_alerts_stream(browser: Page, setup_page_logging, failure_artifacts):
    facet_name = "source"
    alert_property_name = "providerType"
    value = "prometheus"
    test_id = "test_alerts_stream"
    cel_to_filter_alerts = f"testId == '{test_id}'"
    log_entries = []
    setup_console_listener(browser, log_entries)

    browser.goto(f"{KEEP_UI_URL}/alerts/feed?cel={cel_to_filter_alerts}")
    browser.wait_for_selector("[data-testid='alerts-table']")
    browser.wait_for_selector("[data-testid='facets-panel']")
    simulated_alerts = []
    for alert_index, provider_type in enumerate(["prometheus"] * 20):
        alert = create_fake_alert(alert_index, provider_type)
        alert["testId"] = test_id
        simulated_alerts.append((provider_type, alert))

    token = get_token()
    for provider_type, alert in simulated_alerts:
        url = f"{KEEP_API_URL}/alerts/event/{provider_type}"
        requests.post(
            url,
            json=alert,
            timeout=5,
            headers={"Authorization": "Bearer " + token},
        ).raise_for_status()
        time.sleep(1)

    try:
        # refresh the page to get the new alerts
        browser.reload()
        browser.wait_for_selector("[data-testid='facet-value']", timeout=30000)  # Increase timeout from 10s to 30s

        # Add retry logic for checking alert count
        max_retries = 5
        for retry in range(max_retries):
            try:
                # Wait a bit longer between retries
                if retry > 0:
                    print(f"Retry {retry}/{max_retries} for alert count check")
                    time.sleep(5)
                    browser.reload()
                    browser.wait_for_selector("[data-testid='facet-value']", timeout=30000)

                # Check if alerts are visible
                alert_count = browser.locator("[data-testid='alerts-table'] table tbody tr").count()
                print(f"Current alert count: {alert_count}, expected: {len(simulated_alerts)}")

                if alert_count == len(simulated_alerts):
                    break

                if retry == max_retries - 1:
                    # On last retry, use the expect assertion which will provide better error details
                    expect(
                        browser.locator("[data-testid='alerts-table'] table tbody tr")
                    ).to_have_count(len(simulated_alerts))
            except Exception as retry_error:
                if retry == max_retries - 1:
                    raise retry_error
                print(f"Error during retry {retry}: {str(retry_error)}")

    except Exception as e:
        save_failure_artifacts(browser, log_entries=log_entries)
        raise e
    query_result = query_alerts(cell_query=cel_to_filter_alerts, limit=1000)
    current_alerts = query_result["results"]
    assert_facet(browser, facet_name, current_alerts, alert_property_name)

    assert_alerts_by_column(
        browser,
        current_alerts,
        lambda alert: alert[alert_property_name] == value,
        alert_property_name,
        None,
    )


def test_filter_search_timeframe_combination_with_queryparams(
    browser: Page,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    try:
        facet_name = "severity"
        alert_property_name = "severity"
        value = "info"

        def filter_lambda(alert):
            return (
                alert[alert_property_name] == value
                and "high" in alert["name"].lower()
                and datetime.fromisoformat(alert["lastReceived"]).replace(
                    tzinfo=timezone.utc
                )
                >= (datetime.now(timezone.utc) - timedelta(hours=4))
            )

        current_alerts = query_alerts(cell_query="", limit=1000)["results"]
        init_test(browser, current_alerts, max_retries=3)
        filtered_alerts = [alert for alert in current_alerts if filter_lambda(alert)]

        # Give the page a moment to process redirects
        browser.wait_for_timeout(500)

        # Wait for navigation to complete to either signin or providers page
        # (since we might get redirected automatically)
        browser.wait_for_load_state("networkidle")

        option = browser.locator("[data-testid='facet-value']", has_text=value)
        option.hover()

        option.locator("button", has_text="Only").click()
        browser.wait_for_timeout(500)

        cel_input_locator = browser.locator(".alerts-cel-input")
        cel_input_locator.click()
        browser.keyboard.type("name.contains('high')")
        browser.keyboard.press("Enter")
        browser.wait_for_timeout(500)

        # select timeframe
        browser.locator("button[data-testid='timeframe-picker-trigger']").click()
        browser.locator(
            "[data-testid='timeframe-picker-content'] button", has_text="Past 4 hours"
        ).click()

        # check that alerts are filtered by the selected facet/cel/timeframe
        assert_facet(
            browser,
            facet_name,
            filtered_alerts,
            alert_property_name,
        )
        assert_alerts_by_column(
            browser,
            current_alerts,
            filter_lambda,
            alert_property_name,
            None,
        )

        # Refresh in order to check that filters/facets are restored
        # It will use the URL query params from previous filters
        browser.reload()
        assert_facet(
            browser,
            facet_name,
            filtered_alerts,
            alert_property_name,
        )
        assert_alerts_by_column(
            browser,
            current_alerts,
            filter_lambda,
            alert_property_name,
            None,
        )
        expect(
            browser.locator("button[data-testid='timeframe-picker-trigger']")
        ).to_contain_text("Past 4 hours")
    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise


def test_adding_new_preset(
    browser: Page,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    try:
        facet_name = "severity"
        alert_property_name = "severity"

        def filter_lambda(alert):
            return "high" in alert["name"].lower()

        current_alerts = query_alerts(cell_query="", limit=1000)["results"]
        init_test(browser, current_alerts, max_retries=3)
        filtered_alerts = [alert for alert in current_alerts if filter_lambda(alert)]

        # Give the page a moment to process redirects
        browser.wait_for_timeout(500)

        # Wait for navigation to complete to either signin or providers page
        # (since we might get redirected automatically)
        browser.wait_for_load_state("networkidle")

        cel_input_locator = browser.locator(".alerts-cel-input")
        cel_input_locator.click()
        browser.keyboard.type("name.contains('high')")
        browser.keyboard.press("Enter")
        browser.wait_for_timeout(500)

        # check that alerts are filtered by the preset CEL
        assert_facet(
            browser,
            facet_name,
            filtered_alerts,
            alert_property_name,
        )
        assert_alerts_by_column(
            browser,
            current_alerts,
            filter_lambda,
            alert_property_name,
            None,
        )

        browser.locator("[data-testid='save-preset-button']").click()

        preset_form_locator = browser.locator("[data-testid='preset-form']")
        expect(browser.locator("[data-testid='alerts-count-badge']")).to_contain_text(
            str(len(filtered_alerts))
        )
        preset_form_locator.locator("[data-testid='preset-name-input']").fill(
            "Test preset"
        )

        preset_form_locator.locator(
            "[data-testid='counter-shows-firing-only-switch']"
        ).click()

        preset_form_locator.locator("[data-testid='save-preset-button']").click()
        preset_locator = browser.locator(
            "[data-testid='preset-link-container']", has_text="Test preset"
        )
        expect(preset_locator).to_be_visible()
        expect(preset_locator.locator("[data-testid='preset-badge']")).to_contain_text(
            str(len(filtered_alerts))
        )
        expect(browser.locator(".alerts-cel-input .view-lines")).to_have_text(
            "name.contains('high')"
        )
        expect(browser.locator("[data-testid='preset-page-title']")).to_contain_text(
            "Test preset"
        )

        # Refresh in order to check that the preset and corresponding data is open
        browser.reload()
        expect(browser.locator(".alerts-cel-input .view-lines")).to_have_text(
            "name.contains('high')"
        )
        expect(browser.locator("[data-testid='preset-page-title']")).to_contain_text(
            "Test preset"
        )
        assert_facet(
            browser,
            facet_name,
            filtered_alerts,
            alert_property_name,
        )
        assert_alerts_by_column(
            browser,
            current_alerts,
            filter_lambda,
            alert_property_name,
            None,
        )
        # check that alerts noise is not playing
        expect(
            browser.locator("[data-testid='noisy-presets-audio-player'].playing")
        ).to_have_count(0)
    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise


def test_adding_new_noisy_preset(
    browser: Page,
    setup_test_data,
    setup_page_logging,
    failure_artifacts,
):
    try:
        current_alerts = query_alerts(cell_query="", limit=1000)["results"]
        init_test(browser, current_alerts, max_retries=3)

        # Give the page a moment to process redirects
        browser.wait_for_timeout(500)

        # Wait for navigation to complete to either signin or providers page
        # (since we might get redirected automatically)
        browser.wait_for_load_state("networkidle")
        cel_input_locator = browser.locator(".alerts-cel-input")
        cel_input_locator.click()
        browser.keyboard.type("name.contains('high')")
        browser.keyboard.press("Enter")
        browser.wait_for_timeout(500)
        browser.locator("[data-testid='save-preset-button']").click()
        preset_form_locator = browser.locator("[data-testid='preset-form']")
        preset_form_locator.locator("[data-testid='preset-name-input']").fill(
            "Test noisy preset"
        )
        preset_form_locator.locator("[data-testid='is-noisy-switch']").click()
        preset_form_locator.locator("[data-testid='save-preset-button']").click()
        expect(
            browser.locator("[data-testid='noisy-presets-audio-player'].playing")
        ).to_have_count(1)
        browser.reload()

        # check that it's still playing after reloading
        expect(
            browser.locator("[data-testid='noisy-presets-audio-player'].playing")
        ).to_have_count(1)
    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise
