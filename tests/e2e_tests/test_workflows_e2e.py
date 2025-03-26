import os
import re

from playwright.sync_api import Page, expect

from tests.e2e_tests.utils import (
    init_e2e_test,
    save_failure_artifacts,
    setup_console_listener,
    trigger_alert,
)

def test_add_workflow(browser: Page, setup_page_logging, failure_artifacts):
    """
    Test to add a workflow node
    """
    page = browser
    log_entries = []
    setup_console_listener(page, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        page.get_by_role("link", name="Workflows").click()
        page.get_by_role("button", name="Create Workflow").click()
        page.get_by_placeholder("Set the name").click()
        page.get_by_placeholder("Set the name").press("ControlOrMeta+a")
        page.get_by_placeholder("Set the name").fill("Example Console Workflow")
        page.get_by_placeholder("Set the name").press("Tab")
        page.get_by_placeholder("Set the description").fill(
            "Example workflow description"
        )
        page.get_by_test_id("wf-add-trigger-button").first.click()
        page.get_by_text("Manual").click()
        page.get_by_test_id("wf-add-step-button").first.click()
        page.get_by_placeholder("Search...").click()
        page.get_by_placeholder("Search...").fill("cons")
        page.get_by_text("console-action").click()
        page.wait_for_timeout(500)
        page.locator(".react-flow__node:has-text('console-action')").click()
        page.get_by_placeholder("message", exact=True).click()
        page.get_by_placeholder("message", exact=True).fill("Hello world!")
        page.get_by_test_id("wf-editor-configure-save-button").click()
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        expect(page.get_by_test_id("wf-name")).to_contain_text(
            "Example Console Workflow"
        )
        expect(page.get_by_test_id("wf-description")).to_contain_text(
            "Example workflow description"
        )
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise


def test_test_run_workflow(browser: Page):
    """
    Test to test run a workflow
    """
    page = browser
    log_entries = []
    setup_console_listener(page, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        page.get_by_role("link", name="Workflows").click()
        page.get_by_role("button", name="Create Workflow").click()
        page.wait_for_url("http://localhost:3000/workflows/builder")
        page.get_by_placeholder("Set the name").click()
        page.get_by_placeholder("Set the name").press("ControlOrMeta+a")
        page.get_by_placeholder("Set the name").fill("Test Run Workflow")
        page.get_by_placeholder("Set the name").press("Tab")
        page.get_by_placeholder("Set the description").fill(
            "Test Run workflow description"
        )
        page.get_by_test_id("wf-add-trigger-button").first.click()
        page.get_by_text("Manual").click()
        page.get_by_test_id("wf-add-step-button").first.click()
        page.get_by_placeholder("Search...").click()
        page.get_by_placeholder("Search...").fill("cons")
        page.get_by_text("console-action").click()
        page.get_by_placeholder("message", exact=True).click()
        page.get_by_placeholder("message", exact=True).fill("Hello world!")
        page.get_by_test_id("wf-editor-configure-save-button").click()
        page.wait_for_url(re.compile(r"http://localhost:3000/workflows/(?!builder).*"))
        page.get_by_text("Builder").click()
        page.get_by_test_id("wf-builder-main-test-run-button").click()
        page.wait_for_selector("text=Workflow Execution Results")
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise

def test_paste_workflow_yaml_quotes_preserved(browser: Page):
    # browser is actually a page object
    page = browser

    log_entries = []
    setup_console_listener(page, log_entries)

    def get_workflow_yaml(file_name):
        file_path = os.path.join(os.path.dirname(__file__), file_name)
        with open(file_path, "r") as file:
            return file.read()

    workflow_yaml = get_workflow_yaml("workflow-quotes-sample.yaml")

    try:
        init_e2e_test(browser, next_url="/workflows")
        page.get_by_role("button", name="Upload Workflows").click()
        page.get_by_test_id("text-area").click()
        page.get_by_test_id("text-area").fill(workflow_yaml)
        page.get_by_role("button", name="Load", exact=True).click()
        page.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        page.get_by_role("tab", name="YAML Definition").click()
        yaml_editor_container = page.get_by_test_id("wf-detail-yaml-editor-container")
        # Copy the YAML content to the clipboard
        yaml_editor_container.get_by_test_id("copy-yaml-button").click()
        # Get the clipboard content
        clipboard_text = page.evaluate(
            """async () => {
            return await navigator.clipboard.readText();
        }"""
        )
        # Remove all whitespace characters from the YAML content for comparison
        normalized_original = re.sub(r"\s", "", workflow_yaml)
        normalized_clipboard = re.sub(r"\s", "", clipboard_text)
        assert normalized_clipboard == normalized_original
    except Exception:
        save_failure_artifacts(page, log_entries)
        raise



def test_add_upload_workflow_with_alert_trigger(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Workflows").hover()
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-sample.yaml")
        browser.get_by_role("button", name="Upload")
        # new behavior: is redirecting to the detail page of the workflow, so we need to go back to the list page
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        trigger_alert("prometheus")
        browser.wait_for_timeout(2000)
        browser.goto("http://localhost:3000/workflows")
        # wait for prometheus to fire an alert and workflow to run
        browser.reload()
        workflow_card = browser.locator(
            "[data-testid^='workflow-tile-']",
            has_text="test_add_upload_workflow_with_alert_trigger",
        )
        expect(workflow_card).not_to_contain_text("No data available")
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise



def test_monaco_editor_npm(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)
    try:
        init_e2e_test(browser, next_url="/signin")
        browser.route("**/*", lambda route, request:
            route.abort() if not request.url.startswith("http://localhost") else route.continue_()
        )
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-sample-npm.yaml")
        browser.get_by_role("button", name="Upload")
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        browser.get_by_role("tab", name="YAML Definition").click()
        editor_container = browser.get_by_test_id("wf-detail-yaml-editor-container")
        expect(editor_container).not_to_contain_text("Error loading Monaco Editor from CDN")
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise

def test_yaml_editor_yaml_valid(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)

    try:
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-valid-sample.yaml")
        browser.get_by_role("button", name="Upload")
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        browser.get_by_role("tab", name="YAML Definition").click()
        yaml_editor = browser.get_by_test_id("wf-detail-yaml-editor-container")
        expect(yaml_editor).to_be_visible()
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-no-errors").first).to_be_visible()
    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise

def test_yaml_editor_yaml_invalid(browser: Page):
    log_entries = []
    setup_console_listener(browser, log_entries)

    try:
        init_e2e_test(browser, next_url="/signin")
        browser.get_by_role("link", name="Workflows").click()
        browser.get_by_role("button", name="Upload Workflows").click()
        file_input = browser.locator("#workflowFile")
        file_input.set_input_files("./tests/e2e_tests/workflow-invalid-sample.yaml")
        browser.get_by_role("button", name="Upload")
        browser.wait_for_url(re.compile("http://localhost:3000/workflows/.*"))
        browser.get_by_role("tab", name="YAML Definition").click()
        yaml_editor = browser.get_by_test_id("wf-detail-yaml-editor-container")
        expect(yaml_editor).to_be_visible()
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-summary").first).to_contain_text("6 validation errors")
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-list").first).to_contain_text('String is shorter than the minimum length of 1.')
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-list").first).to_contain_text('Missing property "provider".')
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-list").first).to_contain_text('Property provider_invalid_prop is not allowed.')
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-list").first).to_contain_text('Value is not accepted. Valid values: "message", "blocks", "channel", "slack_timestamp", "thread_timestamp", "attachments", "username", "notification_type", "enrich_alert", "enrich_incident".')
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-list").first).to_contain_text('Property enrich_incident is not allowed.')
        expect(yaml_editor.get_by_test_id("wf-yaml-editor-validation-errors-list").first).to_contain_text('Property enrich_alert is not allowed.')

    except Exception:
        save_failure_artifacts(browser, log_entries)
        raise
