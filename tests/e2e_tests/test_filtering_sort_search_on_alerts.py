import os
import random
import time
from datetime import datetime, timedelta
import uuid

import requests
from playwright.sync_api import expect, Browser


os.environ["PLAYWRIGHT_HEADLESS"] = "false"

GRAFANA_HOST = "http://grafana:3000"
GRAFANA_HOST_LOCAL = "http://localhost:3002"
KEEP_UI_URL = "http://localhost:3000"
KEEP_API_URL = "http://localhost:8080"

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
    if provider_type == "datadog":
        title = "Memory leak detected"
        status = "Triggered"
        severity = "P4"

        if index % 4:
            title = "High CPU Usage"
            status = "Recovered"
            severity = "P3"
        elif index % 3:
            title = "Memory Usage High"
            status = "Muted"
            severity = "P2"
        elif index % 2:
            title = "Network Error"

        return {
            "title": f"[{severity}] [{status}] {title} {index}",
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
            "alert_transition": status,
            "timestamp": (datetime.now() + timedelta(minutes=index)).isoformat(),
            "tags": {
                "envNameTag": "production" if index % 2 else "development",
            },
            "id": "bf414194e8622f241c38c645b634d6f18d92c58f56eccafa2e6a2b27b08adf05",
        }


def upload_alerts():
    total_alerts = 20
    current_alerts = query_allerts()

    if query_allerts()["count"] < total_alerts:
        simulated_alerts = []
        for index in range(total_alerts - current_alerts["count"]):
            provider_type = random.choice(["datadog"])
            alert = create_fake_alert(index, provider_type)
            alert["temp_id"] = str(uuid.uuid4())

            simulated_alerts.append(alert)
            url = f"{KEEP_API_URL}/alerts/event/{provider_type}"
            requests.post(
                url,
                json=alert,
                timeout=5,
                headers={"Authorization": "Bearer keep-token-for-no-auth-purposes"},
            )
        attempt = 0
        while True:
            time.sleep(1)
            current_alerts = query_allerts()
            attempt += 1

            if attempt >= 10:
                raise Exception(
                    f"{total_alerts - current_alerts['count']} out of {total_alerts} alerts were not uploaded"
                )

            if len(current_alerts["results"]) == len(simulated_alerts):
                break
    return current_alerts


def init_test(browser: Browser):
    current_alerts = upload_alerts()
    current_alerts_results = current_alerts["results"]

    browser.goto(f"{KEEP_UI_URL}/alerts/feed", timeout=10000)
    browser.wait_for_selector("[data-test-id='facet-value']", timeout=10000)
    browser.wait_for_selector(
        f"text={current_alerts_results[0]['name']}", timeout=10000
    )
    rows_count = browser.locator("[data-test-id='alerts-table'] table tbody tr").count()
    # check that required alerts are loaded and displayed
    assert rows_count == len(current_alerts_results)
    return current_alerts_results


def assert_facet(browser, facet_name, alerts, alert_property_name: str):
    counters_dict = {}
    for alert in alerts:
        if alert[alert_property_name] not in counters_dict:
            counters_dict[alert[alert_property_name]] = 0
        counters_dict[alert[alert_property_name]] += 1

    for facet_value, count in counters_dict.items():
        facet_locator = browser.locator("[data-test-id='facet']", has_text=facet_name)
        expect(facet_locator).to_be_visible()
        facet_value_locator = facet_locator.locator(
            "[data-test-id='facet-value']", has_text=facet_value
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
    filtered_by_status = [alert for alert in alerts if predicate(alert)]
    matched_rows = browser.locator("[data-test-id='alerts-table'] table tbody tr")
    expect(matched_rows).to_have_count(len(filtered_by_status))

    # check that only alerts with selected status are displayed
    for alert in filtered_by_status:
        row_locator = browser.locator(
            "[data-test-id='alerts-table'] table tbody tr", has_text=alert["name"]
        )
        expect(row_locator).to_be_visible()
        column_locator = row_locator.locator("td").nth(column_index)
        expect(column_locator).to_have_text(alert[property_in_alert])


def test_filter(browser):
    current_alerts = init_test(browser)
    status = "suppressed"

    # check existence of default facets
    for facet_name in ["severity", "status", "source", "source", "incident"]:
        expect(
            browser.locator("[data-test-id='facet']", has_text=facet_name)
        ).to_be_visible()

    assert_facet(browser, "status", current_alerts, "status")

    option = browser.locator("[data-test-id='facet-value']", has_text=status)
    option.hover()

    option.locator("button", has_text="Only").click()

    assert_alerts_by_column(
        browser, current_alerts, lambda x: x["status"] == status, "status", 5
    )
