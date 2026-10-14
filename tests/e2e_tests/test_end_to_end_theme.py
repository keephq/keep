import re

from playwright.sync_api import Page, expect

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
                page.get_by_role("button", name="Test alerts", exact=True).click()
                break
            except Exception as e:
                if attempt < max_attemps - 1:
                    print("Failed to load alerts feed page. Retrying...")
                    continue
                else:
                    raise e

        # The dialog root has no layout box; its fixed-position panel contains
        # the visible controls. Wait on a control inside the dialog instead.
        submit_button = page.get_by_role("dialog").get_by_role(
            "button", name="Submit", exact=True
        )
        expect(submit_button).to_be_visible()

        # Using the visible text for dropdown
        page.locator("text=Select alert source").click(force=True)

        # select the "prometheus prometheus" option
        page.get_by_role("option", name="prometheus prometheus").locator("div").click()
        # click the submit button
        submit_button.click()
        expect(submit_button).not_to_be_visible()

        # refresh the page
        page.reload()
        page.wait_for_load_state("networkidle")

        # The alert was submitted above. Open settings directly; clicking an
        # unrelated icon button here can open another dialog or navigation menu.
        page.get_by_test_id("settings-button").click()

        # Wait for settings panel to appear
        page.wait_for_selector('[data-testid="settings-panel"]', state="visible")

        # click the "theme" tab using data-testid
        page.locator('[data-testid="tab-theme"]').click()

        # Wait for theme panel to be visible
        page.wait_for_selector('[data-testid="panel-theme"]', state="visible")

        # Click the Keep tab
        page.get_by_role("tab", name="Keep").click()

        # Click Apply theme button
        page.get_by_role("button", name="Apply theme").click()

        # Check row background color
        row_element = page.get_by_test_id("alerts-table").locator("tbody tr").first
        # Colors for "Keep" theme
        expected_keep_colors = [
            "rgb(255, 247, 237)",
            "rgb(255, 237, 213)",
            "rgb(254, 215, 170)",
            "rgb(253, 186, 116)",
            "rgb(251, 146, 60)",
        ]
        expect(row_element).to_have_css(
            "background-color",
            re.compile("^(" + "|".join(map(re.escape, expected_keep_colors)) + ")$"),
        )

        # Open settings again
        page.get_by_test_id("settings-button").click()

        # Wait for settings panel
        page.wait_for_selector('[data-testid="settings-panel"]', state="visible")

        # Click theme tab
        page.locator('[data-testid="tab-theme"]').click()

        # Click Basic tab
        page.get_by_role("tab", name="Basic").click()

        # Apply theme
        page.get_by_role("button", name="Apply theme").click()

        # Colors for "Basic" theme
        expected_basic_colors = [
            "rgb(254, 202, 202)",
            "rgb(254, 215, 170)",
            "rgb(254, 240, 138)",
            "rgb(187, 247, 208)",
            "rgb(191, 219, 254)",
        ]
        expect(row_element).to_have_css(
            "background-color",
            re.compile("^(" + "|".join(map(re.escape, expected_basic_colors)) + ")$"),
        )

    except Exception:
        save_failure_artifacts(browser)
        raise
