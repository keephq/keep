import time
from datetime import datetime, timedelta

import pytest
import requests
from playwright.sync_api import Page, expect

from tests.e2e_tests.test_end_to_end import (
    init_e2e_test,
    save_failure_artifacts,
    setup_console_listener,
)

# NOTE 2: to run the tests with a browser, uncomment this two lines:
# import os
# os.environ["PLAYWRIGHT_HEADLESS"] = "false"

GRAFANA_HOST = "http://grafana:3000"
GRAFANA_HOST_LOCAL = "http://localhost:3002"
KEEP_UI_URL = "http://localhost:3000"
KEEP_API_URL = "http://localhost:8080"


def query_allerts(cell_query: str = None, limit: int = None, offset: int = None):
    url = f"{KEEP_API_URL}/alerts/query"

    query = {}

    if cell_query:
        query["cel"] = cell_query

    if limit is not None:
        query["limit"] = limit

    if offset is not None:
        query["offset"] = offset

    result: dict = None

    for _ in range(5):
        try:
            response = requests.post(
                url,
                json=query,
                headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
                timeout=5,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to query alerts: {e}")
            time.sleep(1)
            continue

    if result is None:
        raise Exception(f"Failed to query alerts after {5} attempts")

    grouped_alerts_by_name = {}

    for alert in result["results"]:
        grouped_alerts_by_name.setdefault(alert["name"], []).append(alert)

    return {
        "results": result["results"],
        "count": result["count"],
        "grouped_by_name": grouped_alerts_by_name,
    }


def create_fake_alert(index: int, provider_type: str):
    title = "Low Disk Space"
    status = "firing"
    severity = "critical"
    custom_tag = "environment:production"
    test_alert_id = f"alert-finger-print-{index}"

    if index % 4 == 0:
        title = "High CPU Usage"
        status = "resolved"
        severity = "warning"
        custom_tag = "environment:development"
    elif index % 3 == 0:
        title = "Memory Usage High"
        severity = "info"
        custom_tag = "environment:staging"
    elif index % 2 == 0:
        title = "Network Error"
        status = "suppressed"
        severity = "high"
        custom_tag = "environment:custom"

    if index % 5 == 0:
        title += "Enriched"

    if provider_type == "datadog":
        SEVERITIES_MAP = {
            "info": "P4",
            "warning": "P3",
            "high": "P2",
            "critical": "P1",
        }

        STATUS_MAP = {
            "firing": "Triggered",
            "resolved": "Recovered",
            "suppressed": "Muted",
        }
        alert_name = f"[{SEVERITIES_MAP.get(severity, SEVERITIES_MAP['critical'])}] [{STATUS_MAP.get(status, STATUS_MAP['firing'])}] {title} {provider_type} {index}"

        return {
            "alertName": alert_name,
            "title": alert_name,
            "type": "metric alert",
            "query": "avg(last_5m):avg:system.cpu.user{*} by {host} > 90",
            # Leading index is for easier result verification in sort tests
            "message": f"{index} CPU usage is over 90% on srv1-eu1-prod. Searched value: {'even' if index % 2 else 'odd'}",
            "description": "CPU usage is over 90% on srv1-us2-prod.",
            "tagsList": "environment:production,team:backend,monitor,service:api",
            "priority": "P2",
            "monitor_id": test_alert_id,
            "scopes": "srv2-eu1-prod",
            "host.name": "srv2-ap1-prod",
            "last_updated": 1739114561286,
            "alert_transition": STATUS_MAP.get(status, "Triggered"),
            "date_happened": (datetime.utcnow() + timedelta(days=-index)).timestamp(),
            "tags": {
                "envNameTag": "production" if index % 2 else "development",
                "testAlertId": test_alert_id,
            },
            "custom_tags": {
                "env": custom_tag,
            },
            "id": test_alert_id,
        }
    elif provider_type == "prometheus":
        SEVERITIES_MAP = {
            "critical": "critical",
            "high": "error",
            "warning": "warning",
            "info": "info",
            "low": "low",
        }
        STATUS_MAP = {
            "firing": "firing",
            "resolved": "firing",
        }
        alert_name = f"{title} {provider_type} {index} summary"

        return {
            "alertName": alert_name,
            "testAlertId": test_alert_id,
            "summary": alert_name,
            "labels": {
                "severity": SEVERITIES_MAP.get(severity, SEVERITIES_MAP["critical"]),
                "host": "host1",
                "service": "calendar-producer-java-otel-api-dd",
                "instance": "instance2",
                "alertname": alert_name,
            },
            "status": STATUS_MAP.get(status, STATUS_MAP["firing"]),
            "annotations": {
                # Leading index is for easier result verification in sort tests
                "summary": f"{index} {title} {provider_type}. It's not normal for customer_id:acme",
            },
            "startsAt": "2025-02-09T17:26:12.769318+00:00",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://example.com/graph?g0.expr=NetworkLatencyHigh",
            "fingerprint": test_alert_id,
            "custom_tags": {
                "env": custom_tag,
            },
        }


def upload_alerts():
    current_alerts = query_allerts(limit=1000, offset=0)
    simulated_alerts = []

    for alert_index, provider_type in enumerate(["datadog"] * 10 + ["prometheus"] * 10):
        alert = create_fake_alert(alert_index, provider_type)
        alert["dateForTests"] = (
            datetime(2025, 2, 10, 10) + timedelta(days=-alert_index)
        ).isoformat()

        simulated_alerts.append((provider_type, alert))

    not_uploaded_alerts = []

    for provider_type, alert in simulated_alerts:
        if alert["alertName"] not in current_alerts["grouped_by_name"]:
            not_uploaded_alerts.append((provider_type, alert))

    for provider_type, alert in not_uploaded_alerts:
        url = f"{KEEP_API_URL}/alerts/event/{provider_type}"
        requests.post(
            url,
            json=alert,
            timeout=5,
            headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
        ).raise_for_status()
        time.sleep(
            1
        )  # this is important for sorting by lastReceived. We need to have different lastReceived for alerts

    if not not_uploaded_alerts:
        return current_alerts

    attempt = 0
    while True:
        time.sleep(1)
        current_alerts = query_allerts(limit=1000, offset=0)
        attempt += 1

        if all(
            simluated_alert["alertName"] in current_alerts["grouped_by_name"]
            for _, simluated_alert in simulated_alerts
        ):
            break

        if attempt >= 10:
            raise Exception(
                f"Not all alerts were uploaded. Not uploaded alerts: {not_uploaded_alerts}"
            )

    alerts_to_enrich = [
        alert for alert in current_alerts["results"] if "Enriched" in alert["name"]
    ]

    for alert in alerts_to_enrich:
        url = f"{KEEP_API_URL}/alerts/enrich"
        requests.post(
            url,
            json={
                "enrichments": {"status": "enriched status"},
                "fingerprint": alert["fingerprint"],
            },
            timeout=5,
            headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
        ).raise_for_status()

    return query_allerts(limit=1000, offset=0)


def init_test(browser: Page, alerts):
    init_e2e_test(browser, next_url="/alerts/feed")
    base_url = f"{KEEP_UI_URL}/alerts/feed"
    # we don't care about query params
    browser.wait_for_url(lambda url: url.startswith(base_url))
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
    test_data = upload_alerts()
    yield test_data["results"]


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
    log_entries = []
    setup_console_listener(browser, log_entries)

    browser.goto(f"{KEEP_UI_URL}/alerts/feed?cel={cel_to_filter_alerts}")
    expect(browser.locator("[data-testid='alerts-table']")).to_be_visible()
    expect(browser.locator("[data-testid='facets-panel']")).to_be_visible()
    simulated_alerts = []
    for alert_index, provider_type in enumerate(["prometheus"] * 20):
        alert = create_fake_alert(alert_index, provider_type)
        alert["testId"] = test_id
        simulated_alerts.append((provider_type, alert))

    for provider_type, alert in simulated_alerts:
        url = f"{KEEP_API_URL}/alerts/event/{provider_type}"
        requests.post(
            url,
            json=alert,
            timeout=5,
            headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
        ).raise_for_status()
        time.sleep(1)

    try:
        # refresh the page to get the new alerts
        browser.reload()
        browser.wait_for_selector("[data-testid='facet-value']", timeout=10000)
        expect(
            browser.locator("[data-testid='alerts-table'] table tbody tr")
        ).to_have_count(len(simulated_alerts))
    except Exception as e:
        save_failure_artifacts(browser, log_entries=log_entries)
        raise e
    query_result = query_allerts(cell_query=cel_to_filter_alerts, limit=1000)
    current_alerts = query_result["results"]
    assert_facet(browser, facet_name, current_alerts, alert_property_name)

    assert_alerts_by_column(
        browser,
        current_alerts,
        lambda alert: alert[alert_property_name] == value,
        alert_property_name,
        None,
    )
