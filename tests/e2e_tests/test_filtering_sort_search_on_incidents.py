import re
import pytest
from playwright.sync_api import expect, Page
from tests.e2e_tests.incidents_alerts_setup import (
    setup_incidents_alerts,
)
from tests.e2e_tests.utils import init_e2e_test, save_failure_artifacts

KEEP_UI_URL = "http://localhost:3000"


def init_test(browser: Page, incidents, max_retries=3):
    for i in range(max_retries):
        try:
            init_e2e_test(browser, next_url="/incidents")
            base_url = f"{KEEP_UI_URL}/incidents"
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

    browser.wait_for_selector("[data-testid='facet-value']")

    # to select status filters that are initially not selected
    for status in ["resolved", "deleted"]:
        facet_option = (
            browser.locator("[data-testid='facet']", has_text="Status")
            .locator("[data-testid='facet-value']", has_text=status)
            .locator("input[type='checkbox']")
        )
        if facet_option.is_visible() and not facet_option.is_checked():
            facet_option.click()

    # check that required incidents are loaded and displayed
    # other tests may also add alerts, so we need to check that the number of rows is greater than or equal to 20
    expect(
        browser.locator("table[data-testid='incidents-table'] tbody tr")
    ).to_have_count(20)


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

        prop_value = prop_value if isinstance(prop_value, list) else [prop_value]

        for value in prop_value:
            if value not in counters_dict:
                counters_dict[value] = 0

            counters_dict[value] += 1

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


def assert_incidents_by_column(
    browser,
    alerts: list[dict],
    predicate: lambda x: bool,
    property_in_incident: str,
    column_index: int,
):
    filtered_incidents = [alert for alert in alerts if predicate(alert)]
    matched_rows = browser.locator("table[data-testid='incidents-table'] tbody tr")
    expect(matched_rows).to_have_count(len(filtered_incidents))

    # check that only alerts with selected status are displayed
    for incident in filtered_incidents:
        row_locator = browser.locator(
            "table[data-testid='incidents-table'] tbody tr",
            has_text=incident["user_generated_name"],
        )
        expect(row_locator).to_be_visible()

        if column_index is None:
            return

        column_locator = row_locator.locator("td").nth(column_index)
        expect(column_locator).to_have_text(
            re.compile(incident[property_in_incident], re.IGNORECASE)
        )


@pytest.fixture(scope="module")
def setup_test_data():
    print("Setting up test data...")
    yield setup_incidents_alerts()


facet_test_cases = {
    "severity": {
        "incident_property_name": "severity",
        "value": "warning",
    },
    "status": {
        "incident_property_name": "status",
        "column_index": 2,
        "value": "resolved",
    },
    "source": {
        "incident_property_name": "alert_sources",
        "value": "prometheus",
    },
}

@pytest.mark.parametrize("facet_test_case", facet_test_cases.keys())
def test_filter_by_static_facet(browser, facet_test_case, setup_test_data):
    test_case = facet_test_cases[facet_test_case]
    facet_name = facet_test_case
    incident_property_name = test_case["incident_property_name"]
    column_index = test_case.get("column_index", None)
    value = test_case["value"]
    incidents = setup_test_data["incidents"]

    init_test(browser, incidents)

    assert_facet(browser, facet_name, incidents, incident_property_name)

    option = browser.locator("[data-testid='facet-value']", has_text=value)
    option.hover()

    option.locator("button", has_text="Only").click()

    assert_incidents_by_column(
        browser,
        incidents,
        lambda alert: value
        in (
            alert[incident_property_name]
            if isinstance(alert[incident_property_name], list)
            else [alert[incident_property_name]]
        ),
        incident_property_name,
        column_index,
    )

def test_adding_custom_facet_for_alert_field(browser, setup_test_data):
    facet_property_path = "alert.custom_tags.env"
    facet_name = "Custom Env"
    alert_property_name = facet_property_path
    value = "environment:staging"
    current_incidents = setup_test_data["incidents"]
    incidents_alert = setup_test_data["incidents_alert"]
    init_test(browser, current_incidents)

    # region Add custom facet
    browser.locator("button", has_text="Add Facet").click()

    browser.locator("input[placeholder='Enter facet name']").fill(facet_name)
    browser.locator("input[placeholder*='Search columns']").fill(facet_property_path)
    browser.locator("button", has_text=facet_property_path).click()
    browser.locator("button[data-testid='create-facet-btn']").click()
    # endregion

    # region Verify that facet is displayed and has correct facet values with counters
    counters_dict = {}
    expect(
        browser.locator("[data-testid='facet']", has_text=facet_name)
    ).to_be_visible()
    for incident in current_incidents:
        incident_alerts = incidents_alert.get(incident["id"], [])
        seen_values = set()
        for alert in incident_alerts:
            facet_value = alert.get("custom_tags", {}).get("env", "None")

            if facet_value in seen_values:
                continue

            if facet_value not in counters_dict:
                counters_dict[facet_value] = 0

            counters_dict[facet_value] += 1
            seen_values.add(facet_value)

    facet_locator = browser.locator("[data-testid='facet']", has_text=facet_name)

    for facet_value, count in counters_dict.items():
        expect(facet_locator).to_be_visible()
        facet_value_locator = facet_locator.locator(
            "[data-testid='facet-value']", has_text=facet_value
        )
        expect(facet_value_locator).to_be_visible()
        expect(
            facet_value_locator.locator("[data-testid='facet-value-count']")
        ).to_contain_text(str(count))
    # endregion

    # region Select facet value and verify that only incidents with selected value are displayed
    option = facet_locator.locator("[data-testid='facet-value']", has_text=value)
    option.hover()
    option.locator("button", has_text="Only").click()

    assert_incidents_by_column(
        browser,
        current_incidents[:20],
        lambda incident: len(
            list(
                filter(
                    lambda alert: alert.get("custom_tags", {}).get("env", None)
                    == value,
                    incidents_alert.get(incident["id"], []),
                )
            )
        )
        > 0,
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
    # endregion

sort_tescases = {
    "sort by lastReceived asc/dsc": {
        "column_name": "Created at",
        "column_id": "creation_time",
        "sort_callback": lambda alert: alert["creation_time"],
    }
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
    column_id = test_case["column_id"]
    sort_callback = test_case["sort_callback"]
    current_incidents = setup_test_data["incidents"]
    name_column_index = 3
    init_test(browser, current_incidents)
    try:
        expect(
            browser.locator("table[data-testid='incidents-table'] tbody tr")
        ).to_have_count(len(current_incidents))
    except Exception:
        save_failure_artifacts(browser, log_entries=[])
        raise

    if column_id == "creation_time":
        browser.locator(
            f"table[data-testid='incidents-table'] thead th [data-testid='sort-direction-{column_id}']",
        ).click()  # to reset default sorting by creation_time to no sorting

    for sort_direction_title in ["Sort ascending", "Sort descending"]:
        sorted_alerts = sorted(current_incidents, key=sort_callback)

        if sort_direction_title == "Sort descending":
            sorted_alerts = list(reversed(sorted_alerts))

        column_sort_direction_locator = browser.locator(
            f"table[data-testid='incidents-table'] thead th [data-testid='sort-direction-{column_id}']",
        )
        expect(column_sort_direction_locator).to_be_visible()
        column_sort_direction_locator.click()
        rows = browser.locator("table[data-testid='incidents-table'] tbody tr")

        number_of_missmatches = 0
        for index, incident in enumerate(sorted_alerts):
            row_locator = rows.nth(index)
            column_locator = row_locator.locator("td").nth(name_column_index)
            try:
                expect(column_locator).to_contain_text(incident["user_generated_name"])
            except Exception as e:
                save_failure_artifacts(browser, log_entries=[])
                number_of_missmatches += 1
                if number_of_missmatches > 2:
                    raise e
                else:
                    print(
                        f"Expected: {incident['user_generated_name']} but got: {column_locator.text_content()}"
                    )
                    continue
