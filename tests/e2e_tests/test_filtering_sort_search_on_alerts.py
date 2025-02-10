import os
import random
import time
from datetime import datetime, timedelta
import uuid

import pytest
import requests
from playwright.sync_api import expect, Browser


os.environ["PLAYWRIGHT_HEADLESS"] = "false"

GRAFANA_HOST = "http://grafana:3000"
GRAFANA_HOST_LOCAL = "http://localhost:3002"
KEEP_UI_URL = "http://localhost:3000"
KEEP_API_URL = "http://localhost:8080"

test_run_id = str(uuid.uuid4())

def query_allerts(
    cell_query: str = None,
):
    url = f"{KEEP_API_URL}/alerts/query"

    query_params = {}

    if cell_query:
        query_params["cel"] = cell_query

    if query_params:
        url += "?" + "&".join([f"{k}={v}" for k, v in query_params.items()])

    return requests.get(
        url,
        headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
        timeout=5,
    ).json()


def create_fake_alert(index: int, provider_type: str):
    title = "Low Disk Space"
    status = "firing"
    severity = "critical"
    custom_tag = "environment:production"

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

        return {
            "title": f"[{SEVERITIES_MAP.get(severity, SEVERITIES_MAP['critical'])}] [{STATUS_MAP.get(status, STATUS_MAP['firing'])}] {title} {provider_type} {index}",
            "type": "metric alert",
            "query": "avg(last_5m):avg:system.cpu.user{*} by {host} > 90",
            "message": f"CPU usage is over 90% on srv1-eu1-prod. Searched value: {'even' if index % 2 else 'odd'}",
            "description": "CPU usage is over 90% on srv1-us2-prod.",
            "tagsList": "environment:production,team:backend,monitor,service:api",
            "priority": "P2",
            "monitor_id": f"1234567890-{index}",
            "scopes": "srv2-eu1-prod",
            "host.name": "srv2-ap1-prod",
            "last_updated": 1739114561286,
            "alert_transition": STATUS_MAP.get(status, "Triggered"),
            "date_happened": (datetime.utcnow() + timedelta(days=-index)).timestamp(),
            "tags": {
                "envNameTag": "production" if index % 2 else "development",
            },
            "custom_tags": {
                "env": custom_tag,
            },
            "id": "bf414194e8622f241c38c645b634d6f18d92c58f56eccafa2e6a2b27b08adf05",
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

        return {
            "summary": f"{title} {provider_type} {index} summary",
            "labels": {
                "severity": SEVERITIES_MAP.get(severity, SEVERITIES_MAP["critical"]),
                "host": "host1",
                "service": "calendar-producer-java-otel-api-dd",
                "instance": "instance2",
                "alertname": f"{title} {provider_type} {index}",
            },
            "status": STATUS_MAP.get(status, STATUS_MAP["firing"]),
            "annotations": {
                "summary": f"{title} {provider_type} {index}. It's not normal for customer_id:acme"
            },
            "startsAt": "2025-02-09T17:26:12.769318+00:00",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://example.com/graph?g0.expr=NetworkLatencyHigh",
            "fingerprint": str(uuid.uuid4()),
            "custom_tags": {
                "env": custom_tag,
            },
        }


def upload_alerts():
    total_alerts = 20
    current_alerts = query_allerts()

    if current_alerts["count"] >= total_alerts:
        return current_alerts

    simulated_alerts = []

    for alert_index, provider_type in enumerate(["datadog"] * 10 + ["prometheus"] * 10):
        alert = create_fake_alert(alert_index, provider_type)
        alert["temp_id"] = str(uuid.uuid4())
        alert["dateForTests"] = (
            datetime(2025, 2, 10, 10) + timedelta(days=-alert_index)
        ).isoformat()
        # Tests will open the page with the CEL query for this test_run_id
        alert["test_run_id"] = test_run_id

        simulated_alerts.append((provider_type, alert))

    for provider_type, alert in simulated_alerts:
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

    attempt = 0
    while True:
        time.sleep(1)
        current_alerts = query_allerts()
        attempt += 1

        if attempt >= 10:
            raise Exception(
                f"{total_alerts - current_alerts['count']} out of {total_alerts} alerts were not uploaded"
            )

        if len(current_alerts["results"]) >= len(simulated_alerts):
            break
    return current_alerts


def init_test(browser: Browser):
    current_alerts = upload_alerts()
    current_alerts_results = current_alerts["results"]

    browser.goto(
        f"{KEEP_UI_URL}/alerts/feed?cel=test_run_id == 'test_run_id'", timeout=10000
    )
    browser.wait_for_selector("[data-testid='facet-value']", timeout=10000)
    browser.wait_for_selector(
        f"text={current_alerts_results[0]['name']}", timeout=10000
    )
    rows_count = browser.locator("[data-testid='alerts-table'] table tbody tr").count()
    # check that required alerts are loaded and displayed
    assert rows_count == len(current_alerts_results)
    return current_alerts_results


def select_one_facet_option(browser, facet_name, option_name):
    expect(
        browser.locator("[data-testid='facet']", has_text=facet_name)
    ).to_be_visible()
    option = browser.locator("[data-testid='facet-value']", has_text=option_name)
    option.hover()
    option.locator("button", has_text="Only").click()


def assert_facet(browser, facet_name, alerts, alert_property_name: str):
    counters_dict = {}
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
        expect(facet_value_locator).to_contain_text(str(count))


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


@pytest.mark.parametrize("facet_test_case", facet_test_cases.keys())
def test_filter_by_static_facet(browser, facet_test_case):
    test_case = facet_test_cases[facet_test_case]
    facet_name = facet_test_case
    alert_property_name = test_case["alert_property_name"]
    column_index = test_case.get("column_index", None)
    value = test_case["value"]
    current_alerts = init_test(browser)

    expect(
        browser.locator("[data-testid='facet']", has_text=facet_name)
    ).to_be_visible()

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


def test_adding_custom_facet(browser):
    facet_property_path = "custom_tags.env"
    facet_name = "Custom Env"
    alert_property_name = facet_property_path
    value = "environment:staging"
    current_alerts = init_test(browser)

    browser.locator("button", has_text="Add Facet").click()

    browser.locator("input[placeholder='Enter facet name']").fill(facet_name)
    browser.locator("input[placeholder*='Search columns']").fill(facet_property_path)
    browser.locator("button", has_text=facet_property_path).click()
    browser.locator("button", has_text="Create").click()

    expect(
        browser.locator("[data-testid='facet']", has_text=facet_name)
    ).to_be_visible()

    assert_facet(browser, facet_name, current_alerts, alert_property_name)

    option = browser.locator("[data-testid='facet-value']", has_text=value)
    option.hover()
    option.locator("button", has_text="Only").click()

    assert_alerts_by_column(
        browser,
        current_alerts,
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

    print("f")


search_by_cel_tescases = {
    "contains for nested property": {
        "cel_query": "labels.service.contains('java-otel')",
        "predicate": lambda alert: "java-otel"
        in alert.get("labels", {}).get("service", ""),
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
def test_search_by_cel(browser, search_test_case):
    test_case = search_by_cel_tescases[search_test_case]
    cel_query = test_case["cel_query"]
    predicate = test_case["predicate"]
    alert_property_name = test_case["alert_property_name"]
    current_alerts = init_test(browser)
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
        "sort_callback": lambda alert: alert["lastReceived"],
    },
    "sort by description asc/dsc": {
        "column_name": "description",
        "sort_callback": lambda alert: alert["description"],
    },
}


@pytest.mark.parametrize("sort_test_case", sort_tescases.keys())
def test_sort_asc_dsc(browser, sort_test_case):
    test_case = sort_tescases[sort_test_case]
    coumn_name = test_case["column_name"]
    sort_callback = test_case["sort_callback"]
    current_alerts = init_test(browser)
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
            "[data-testid='alerts-table'] table thead th", has_text=coumn_name
        )
        expect(column_header_locator).to_be_visible()
        column_sort_indicator_locator = column_header_locator.locator(
            f"[title='{sort_direction_title}'] svg"
        )
        expect(column_sort_indicator_locator).to_be_visible()

        column_sort_indicator_locator.click()
        rows = browser.locator("[data-testid='alerts-table'] table tbody tr")

        for index, alert in enumerate(sorted_alerts):
            row_locator = rows.nth(index)
            # 3 is index of "name" column
            column_locator = row_locator.locator("td").nth(3)
            expect(column_locator).to_have_text(alert["name"])
