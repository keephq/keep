import re, os, sys, time
import requests

from datetime import datetime
from playwright.sync_api import expect

# Dear developer, thank you for checking E2E tests!
# For instructions, please check test_end_to_end.py. 

os.environ["PLAYWRIGHT_HEADLESS"] = "false"

def test_pulling_prometheus_alerts_to_provider(browser):
    try: 
        provider_name = "playwright_test_" + datetime.now().strftime("%Y%m%d%H%M%S")

        # Wait for prometheus to wake up and evaluate alert rule as "firing"
        alerts = None
        while alerts is None or \
                len(alerts["data"]["alerts"]) == 0 or \
                alerts["data"]["alerts"][0]['state'] != "firing":        
            print("Waiting for prometheus to fire an alert...")
            time.sleep(1)
            alerts = requests.get("http://localhost:9090/api/v1/alerts").json()
            print(alerts)
        
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

        if os.getenv("GITHUB_ACTIONS") == "true":
            browser.get_by_placeholder("Enter url").fill("http://prometheus-server-for-test-target:9090/")
        else:
            browser.get_by_placeholder("Enter url").fill("http://localhost:9090/")

        browser.mouse.wheel(1000, 10000)  # Scroll down.
        browser.get_by_role("button", name="Connect").click()
        

        # Validate provider is created
        expect(browser.locator("div").filter(has_text=re.compile(re.escape(provider_name))).first).to_be_visible()

        browser.reload()
        
        # Check if alerts were pulled
        for i in range(0, 5):
            browser.get_by_role("link", name="Feed").click()
            browser.wait_for_timeout(5000) # Wait for alerts to be loaded

        browser.reload()

        # Make sure we pulled multiple instances of the alert
        browser.get_by_text("AlwaysFiringAlert").click()
    
        # Delete provider 
        browser.get_by_role("link", name="Providers").click()
        browser.locator("div").filter(has_text=re.compile(re.escape(provider_name))).first.hover()
        browser.locator(".tile-basis").first.click()
        browser.once("dialog", lambda dialog: dialog.accept())
        browser.get_by_role("button", name="Delete").click()

        # Assert provider was deleted
        expect(browser.locator("div").filter(has_text=re.compile(re.escape(provider_name))).first).not_to_be_visible()
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
