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

        # Using the visible text for dropdown
        page.locator("text=Select alert source").click(force=True)

        # select the "prometheus prometheus" option
        page.get_by_role("option", name="prometheus prometheus").locator("div").click()
        # click the submit button
        page.get_by_role("button", name="Submit").click()

        # refresh the page
        page.reload()
        page.wait_for_load_state("networkidle")

        # Click test alerts button using data-testid
        try:
            page.locator('[data-testid="test-alerts-button"]').click()
        except Exception:
            # Fallback to previous methods if test ID isn't found
            try:
                page.get_by_role("button", name="Test alerts").click()
            except Exception:
                try:
                    page.locator("button:has(svg[viewBox='0 0 24 24'])").nth(0).click()
                except Exception:
                    try:
                        page.locator("button.ml-2:has(svg)").nth(0).click()
                    except Exception:
                        page.evaluate(
                            """
                            () => {
                                const buttons = Array.from(document.querySelectorAll('button'));
                                const testButton = buttons.find(b =>
                                    b.innerHTML.includes('svg') &&
                                    b.className.includes('ml-2')
                                );
                                if (testButton) testButton.click();
                            }
                            """
                        )

        # open the settings modal using data-testid
        try:
            page.locator('[data-testid="settings-button"]').click()
        except Exception:
            # Fallback strategies if the test ID isn't found yet
            try:
                page.get_by_role("button", name="Settings").click()
            except Exception:
                try:
                    # Look for a button with settings icon
                    page.locator(
                        'button:has(svg path[d^="M19.4 15a1.65 1.65 0 0 0 .33 1.82"])'
                    ).click()
                except Exception:
                    # Fallback to finding by icon
                    page.locator("button:has(svg)").nth(0).click()

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
        row_element = page.locator("tr.tremor-TableRow-row").nth(1)
        background_color = row_element.evaluate(
            """element => {
            const style = window.getComputedStyle(element);
            return style.backgroundColor;
        }"""
        )
        # Colors for "Keep" theme
        expected_keep_colors = [
            "rgb(255, 247, 237)",
            "rgb(255, 237, 213)",
            "rgb(254, 215, 170)",
            "rgb(253, 186, 116)",
            "rgb(251, 146, 60)",
        ]
        assert (
            background_color in expected_keep_colors
        ), f"Expected {expected_keep_colors}, got {background_color}"

        # Open settings again
        try:
            page.locator('[data-testid="settings-button"]').click()
        except Exception:
            page.get_by_role("button", name="Settings").click()

        # Wait for settings panel
        page.wait_for_selector('[data-testid="settings-panel"]', state="visible")

        # Click theme tab
        page.locator('[data-testid="tab-theme"]').click()

        # Click Basic tab
        page.get_by_role("tab", name="Basic").click()

        # Apply theme
        page.get_by_role("button", name="Apply theme").click()

        # Check row background color again
        row_element = page.locator("tr.tremor-TableRow-row").nth(1)
        background_color = row_element.evaluate(
            """element => {
            const style = window.getComputedStyle(element);
            return style.backgroundColor;
        }"""
        )

        # Colors for "Basic" theme
        expected_basic_colors = [
            "rgb(254, 202, 202)",
            "rgb(254, 215, 170)",
            "rgb(254, 240, 138)",
            "rgb(187, 247, 208)",
            "rgb(191, 219, 254)",
        ]
        assert (
            background_color in expected_basic_colors
        ), f"Expected {expected_basic_colors}, got {background_color}"

    except Exception:
        save_failure_artifacts(browser)
        raise
