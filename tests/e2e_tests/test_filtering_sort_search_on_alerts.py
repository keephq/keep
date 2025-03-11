import time
from datetime import datetime, timedelta

import pytest
from playwright.sync_api import expect, Page
from tests.e2e_tests.incidents_alerts_setup import (
    query_alerts,
    setup_incidents_alerts,
    upload_alert,
    create_fake_alert,
)

KEEP_UI_URL = "http://localhost:3000"

def init_test(browser: Page, alerts):
    url = f"{KEEP_UI_URL}/alerts/feed"
    browser.goto(url)
    browser.wait_for_url(url)
    browser.wait_for_selector("[data-testid='facet-value']", timeout=10000)
    browser.wait_for_selector(f"text={alerts[0]['name']}", timeout=10000)
    rows_count = browser.locator("[data-testid='alerts-table'] table tbody tr").count()
    # check that required alerts are loaded and displayed
    # other tests may also add alerts, so we need to check that the number of rows is greater than or equal to 20
    assert rows_count >= 20
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
        expect(
            facet_value_locator.locator("[data-testid='facet-value-count']")
        ).to_contain_text(str(count))


def assert_alerts_by_column(
    browser,
    alerts: list[dict],
    predicate: lambda x: bool,
    property_in_alert: str,
    column_index: int,
):
    filtered_alerts = [alert for alert in alerts if predicate(alert)]
    matched_rows = browser.locator("[data-testid='alerts-table'] table tbody tr")
    expect(matched_rows).to_have_count(len(filtered_alerts))

    # check that only alerts with selected status are displayed
    for alert in filtered_alerts:
        row_locator = browser.locator(
            "[data-testid='alerts-table'] table tbody tr", has_text=alert["name"]
        )
        expect(row_locator).to_be_visible()

        if column_index is None:
            return

        column_locator = row_locator.locator("td").nth(column_index)
        expect(column_locator).to_have_text(alert[property_in_alert])


facet_test_cases = {
    "severity": {
        "alert_property_name": "severity",
        "value": "high",
    },
    "status": {
        "alert_property_name": "status",
        "column_index": 5,
        "value": "suppressed",
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
def test_filter_by_static_facet(browser, facet_test_case, setup_test_data):
    test_case = facet_test_cases[facet_test_case]
    facet_name = facet_test_case
    alert_property_name = test_case["alert_property_name"]
    column_index = test_case.get("column_index", None)
    value = test_case["value"]
    current_alerts = setup_test_data

    for alert in current_alerts:
        if "Enriched" in alert["name"]:
            # this is a workaround due to a bug in the backend
            # that does not overwrite default fields with enrichment fields
            # but facets work correctly
            alert["status"] = "enriched status"

    init_test(browser, current_alerts)

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


def test_adding_custom_facet(browser, setup_test_data):
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
    },
    "using enriched field": {
        "cel_query": "status == 'enriched status'",
        "predicate": lambda alert: "Enriched" in alert["name"],
        "alert_property_name": "name",
    },
    "date comparison greater than or equal": {
        "cel_query": f"dateForTests >= '{(datetime(2025, 2, 10, 10) + timedelta(days=-14)).isoformat()}'",
        "predicate": lambda alert: alert.get("dateForTests")
        and datetime.fromisoformat(alert.get("dateForTests"))
        >= (datetime(2025, 2, 10, 10) + timedelta(days=-14)),
        "alert_property_name": "name",
    },
}


@pytest.mark.parametrize("search_test_case", search_by_cel_tescases.keys())
def test_search_by_cel(browser, search_test_case, setup_test_data):
    test_case = search_by_cel_tescases[search_test_case]
    cel_query = test_case["cel_query"]
    predicate = test_case["predicate"]
    alert_property_name = test_case["alert_property_name"]
    current_alerts = setup_test_data
    init_test(browser, current_alerts)
    search_input = browser.locator(
        "textarea[placeholder*='Use CEL to filter your alerts']"
    )
    expect(search_input).to_be_visible()
    browser.wait_for_timeout(1000)
    search_input.fill(cel_query)
    search_input.press("Enter")

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
def test_sort_asc_dsc(browser, sort_test_case, setup_test_data):
    test_case = sort_tescases[sort_test_case]
    coumn_name = test_case["column_name"]
    column_id = test_case["column_id"]
    sort_callback = test_case["sort_callback"]
    current_alerts = setup_test_data
    init_test(browser, current_alerts)
    filtered_alerts = [
        alert for alert in current_alerts if alert["providerType"] == "prometheus"
    ]
    select_one_facet_option(browser, "source", "prometheus")
    expect(
        browser.locator("[data-testid='alerts-table'] table tbody tr")
    ).to_have_count(len(filtered_alerts))

    for sort_direction_title in ["Sort ascending", "Sort descending"]:
        sorted_alerts = sorted(filtered_alerts, key=sort_callback)

        if sort_direction_title == "Sort descending":
            sorted_alerts = list(reversed(sorted_alerts))

        column_header_locator = browser.locator(
            f"[data-testid='alerts-table'] table thead th [data-testid='header-cell-{column_id}']",
            has_text=coumn_name,
        )
        expect(column_header_locator).to_be_visible()
        column_header_locator.click()
        rows = browser.locator("[data-testid='alerts-table'] table tbody tr")

        for index, alert in enumerate(sorted_alerts):
            row_locator = rows.nth(index)
            # 3 is index of "name" column
            column_locator = row_locator.locator("td").nth(3)
            expect(column_locator).to_have_text(alert["name"])


def test_alerts_stream(browser):
    facet_name = "source"
    alert_property_name = "providerType"
    value = "prometheus"
    test_id = "test_alerts_stream"
    cel_to_filter_alerts = f"testId == '{test_id}'"

    browser.goto(f"{KEEP_UI_URL}/alerts/feed?cel={cel_to_filter_alerts}")
    expect(browser.locator("[data-testid='alerts-table']")).to_be_visible()
    expect(browser.locator("[data-testid='facets-panel']")).to_be_visible()
    simulated_alerts = []
    for alert_index, provider_type in enumerate(["prometheus"] * 20):
        alert = create_fake_alert(alert_index, provider_type)
        alert["testId"] = test_id
        simulated_alerts.append((provider_type, alert))

    for provider_type, alert in simulated_alerts:
        upload_alert(provider_type, alert)
        time.sleep(1)

    expect(
        browser.locator("[data-testid='alerts-table'] table tbody tr")
    ).to_have_count(len(simulated_alerts))
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
