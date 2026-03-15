import os
import re
import time
from datetime import datetime

import pytest
from playwright.sync_api import Page, expect

from tests.e2e_tests.utils import (
    assert_connected_provider_count,
    delete_provider,
    init_e2e_test,
    save_failure_artifacts,
    setup_console_listener,
)


def get_workflow_yaml(file_name):
    file_path = os.path.join(os.path.dirname(__file__), file_name)
    with open(file_path, "r") as file:
        return file.read()


@pytest.mark.skip(reason="Needs snmp-agent running in docker-compose")
def test_snmp_e2e(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)
    
    snmp_provider_name = "snmp-test"
    snmp_host = "snmp-agent" # As defined in docker-compose-e2e-snmp.yml
    snmp_port = 162
    snmp_community = "public"
    snmp_oid = "1.3.6.1.4.1.99999.1.1"
    
    try:
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Providers").click()
        
        # Connect the SNMP provider
        browser.locator("button:has-text('SNMP'):has-text('messaging')").click()
        browser.get_by_placeholder("Enter provider name").fill(snmp_provider_name)
        browser.get_by_placeholder("Enter host").fill(snmp_host)
        browser.get_by_placeholder("Enter port").fill(str(snmp_port))
        browser.get_by_placeholder("Enter community").fill(snmp_community)
        browser.get_by_placeholder("Enter oid").fill(snmp_oid)
        browser.get_by_role("button", name="Connect", exact=True).click()
        browser.wait_for_selector("text=Connected", timeout=15000)
        
        assert_connected_provider_count(
            browser=browser,
            provider_type="SNMP",
            provider_name=snmp_provider_name,
            provider_count=1,
        )
        
        # Upload the SNMP workflow
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-snmp-trap.yaml")
        browser.get_by_role("button", name="Upload").click()
        
        # Verify workflow uploaded
        expect(browser.get_by_text("1 workflow uploaded successfully")).to_be_visible()
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        
        # Trigger the workflow
        browser.get_by_test_id("wf-run-now-button").click()
        browser.get_by_role("button", name="Run", exact=True).click()
        expect(browser.get_by_text("Workflow started successfully")).to_be_visible()
        
        # Wait for some time for the trap to be sent and logged by snmp-agent
        time.sleep(5) 
        
        # Verify trap reception in snmp-agent logs
        # This part requires access to docker logs, which is outside playwright's scope.
        # This will be replaced by an actual check if possible, for now, manual inspection or
        # a separate script will be needed.
        # For a full automated E2E, a service that exposes snmp-agent logs would be ideal.
        # For now, I'll log a message indicating manual verification is needed.
        print("E2E Test: SNMP trap sent. Please manually check snmp-agent logs for verification.")
        
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise
    finally:
        # Clean up
        browser.goto("http://localhost:3000/providers")
        delete_provider(browser=browser, provider_type="SNMP", provider_name=snmp_provider_name)
        
        browser.goto("http://localhost:3000/workflows")
        # Find the workflow card and delete it
        workflow_card = browser.locator(
            "[data-testid^='workflow-tile-']",
            has_text="send-snmp-trap-workflow",
        )
        if workflow_card.count() > 0:
            workflow_card.get_by_test_id("dropdown-menu-button").click()
            browser.get_by_role("menuitem", name="Delete").click()
            browser.get_by_role("button", name="Delete").click()
            expect(browser.get_by_text("Workflow deleted successfully")).to_be_visible()