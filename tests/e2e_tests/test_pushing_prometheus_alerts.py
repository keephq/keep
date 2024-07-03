import re, os, sys

from datetime import datetime
from playwright.sync_api import expect

# Dear developer, thank you for checking E2E tests!
# For instructions, please check test_end_to_end.py. 

os.environ["PLAYWRIGHT_HEADLESS"] = "false"

def test_pulling_prometheus_alerts_to_provider(browser):
    try: 
        provider_name = "playwright_test_" + datetime.now().strftime("%Y%m%d%H%M%S")

        # Create prometheus provider 
        browser.goto("http://localhost:3000/providers")
        browser.get_by_placeholder("Filter providers...").click()
        browser.get_by_placeholder("Filter providers...").fill("prometheus")
        browser.get_by_placeholder("Filter providers...").press("Enter")
        browser.get_by_text("Available Providers").hover()
        browser.locator("div").filter(has_text=re.compile(r"^prometheus dataalertConnect$")).nth(1).hover()
        
        browser.get_by_role("button", name="Connect").click()
        browser.get_by_placeholder("Enter provider name").click()
        browser.get_by_placeholder("Enter provider name").fill(provider_name)
        browser.get_by_placeholder("Enter url").click()
        browser.get_by_placeholder("Enter url").fill("http://prometheus-server-for-test-target:9090/")
        browser.get_by_role("button", name="Connect").click()

        browser.reload()

        # Check if alerts were pulled
        browser.get_by_role("link", name="Feed").click()

        # Open history
        browser.get_by_text("AlwaysFiringAlert").hover()
        browser.mouse.wheel(1000, 0)  # Scroll right to find the button.
        browser.get_by_title("Alert actions").first.click()
        browser.get_by_role("menuitem", name="History").click()
        
        # Wait for history to load
        browser.get_by_text("History of: AlwaysFiringAlert").hover()

        # Make sure we pulled multiple instances of the alert
        assert browser.get_by_text("AlwaysFiringAlert").count() > 1
        browser.get_by_role("button", name="Close").click()
    
        # Delete provider 
        browser.get_by_role("link", name="Providers").click()
        browser.locator("div").filter(has_text=re.compile(r"^Connectedprometheus id: " + re.escape(provider_name) + r"Modify$")).first.click()
        browser.get_by_text("Push alerts from Prometheus").hover()
        browser.once("dialog", lambda dialog: dialog.accept())
        browser.get_by_role("button", name="Delete").click()

        # Assert provider was deleted
        expect(browser.locator("div").filter(has_text=re.compile(r"^Connectedprometheus id: " + re.escape(provider_name) + r"Modify$")).first).not_to_be_visible()
    except Exception:
        # Current file + test name for unique html and png dump.
        current_test_name = \
            "playwright_dump_" + \
            os.path.basename(__file__)[:-3] + \
            "_" + sys._getframe().f_code.co_name

        browser.screenshot(path=current_test_name + ".png")
        with open(current_test_name + ".html", "w") as f:
            f.write(browser.content())

        raise
