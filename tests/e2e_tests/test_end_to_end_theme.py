import time

from playwright.sync_api import Page

from tests.e2e_tests.utils import init_e2e_test, save_failure_artifacts


def test_start_with_keep_db(browser: Page, setup_page_logging, failure_artifacts):
    init_e2e_test(browser, next_url="/alerts/feed")
    page = browser if hasattr(browser, "goto") else browser.page
    try:
        # wait a second
        time.sleep(1)
        # open the form
        page.locator(".h-14 > div > button").click()

        # wait for the modal to appear
        page.wait_for_selector("div[data-headlessui-state='open']")

        # More stable approaches for the dropdown:
        # 1. Using the visible text - most reliable
        page.locator("text=Select alert source").click(force=True)

        # select the "prometheus prometheus" option
        page.get_by_role("option", name="prometheus prometheus").locator("div").click()
        # click the submit button
        page.get_by_role("button", name="Submit").click()

        # refresh the page
        page.reload()
        # click the "select alert source" dropdown
        page.locator('[id="headlessui-popover-button-«ra»"]').click()

        # click the "theme" tab
        page.get_by_role("tab", name="Theme").click()
        page.get_by_role("tab", name="Keep").click()
        page.get_by_role("button", name="Apply theme").click()
        row_element = page.locator("tr.tremor-TableRow-row").nth(1)
        background_color = row_element.evaluate(
            """element => {
            const style = window.getComputedStyle(element);
            return style.backgroundColor;
        }"""
        )
        # bg-orange-100
        assert background_color == "rgb(255, 247, 237)"
        # click the "select alert source" dropdown
        page.locator('[id="headlessui-popover-button-«ra»"]').click()
        page.get_by_role("tab", name="Theme").click()
        page.get_by_role("tab", name="Basic").click()
        page.get_by_role("button", name="Apply theme").click()

        row_element = page.locator("tr.tremor-TableRow-row").nth(1)
        # Get the computed background color in RGB format
        background_color = row_element.evaluate(
            """element => {
            const style = window.getComputedStyle(element);
            return style.backgroundColor;
        }"""
        )

        # Check if the color matches the bg-blue-200
        expected_color = "rgb(191, 219, 254)"
        assert (
            background_color == expected_color
        ), f"Expected {expected_color}, got {background_color}"

    except Exception:
        save_failure_artifacts(browser)
        raise
