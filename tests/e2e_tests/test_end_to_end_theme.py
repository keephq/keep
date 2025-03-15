from playwright.sync_api import Page

from tests.e2e_tests.utils import init_e2e_test, save_failure_artifacts


def test_theme(browser: Page, setup_page_logging, failure_artifacts):
    page = browser if hasattr(browser, "goto") else browser.page
    try:
        # let the page load
        max_attemps = 3
        for attempt in range(3):
            try:
                init_e2e_test(browser, next_url="/alerts/feed")
                browser.wait_for_timeout(10000)
                browser.wait_for_load_state("networkidle")
                page.locator(".h-14 > div > button").click()
                break
            except Exception as e:
                if attempt < max_attemps - 1:
                    print("Failed to load alerts feed page. Retrying...")
                    continue
                else:
                    raise e

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
        # critical: "bg-orange-400", // Highest opacity for critical
        # high: "bg-orange-300",
        # warning: "bg-orange-200",
        # low: "bg-orange-100",
        # info: "bg-orange-50", // Lowest opacity for info
        assert background_color in [
            "rgb(255, 247, 237)",
            "rgb(255, 237, 213)",
            "rgb(254, 215, 170)",
            "rgb(253, 186, 116)",
            "rgb(251, 146, 60)",
        ]
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

        # critical: "bg-red-200",
        # high: "bg-orange-200",
        # warning: "bg-yellow-200",
        # low: "bg-green-200",
        # info: "bg-blue-200",
        expected_colors = [
            "rgb(254, 202, 202)",
            "rgb(254, 215, 170)",
            "rgb(254, 240, 138)",
            "rgb(187, 247, 208)",
            "rgb(191, 219, 254)",
        ]
        assert (
            background_color in expected_colors
        ), f"Expected {expected_colors}, got {background_color}"

    except Exception:
        save_failure_artifacts(browser)
        raise
