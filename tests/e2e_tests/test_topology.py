import os

from playwright.sync_api import expect, Page

# Importing utilities for test assertions and setup

# Setting Playwright to run in non-headless mode for debugging purposes
os.environ["PLAYWRIGHT_HEADLESS"] = "false"

# Base URL of the application under test
KEEP_UI_URL = "http://localhost:3000"


def test_topology_manual(browser: Page, setup_page_logging, failure_artifacts):
    # Navigate to sign-in page
    browser.goto(f"{KEEP_UI_URL}/signin")
    browser.wait_for_url(f"{KEEP_UI_URL}/incidents")

    # Open the Service Topology page
    browser.get_by_role("link", name="Service Topology").hover()
    browser.get_by_role("link", name="Service Topology").click()

    max_retries = 5
    retries = 0

    # Attempt to add a new service node, retrying in case of failure
    while retries <= max_retries:
        try:
            browser.get_by_role("button", name="Add Node", exact=True).click()
            browser.get_by_placeholder("Enter service here...").fill("service_id_1")
            break
        except Exception:
            if retries == max_retries:
                raise
            retries += 1
            browser.reload()

    # Ensure Save button is disabled when required fields are empty
    expect(browser.get_by_role("button", name="Save", exact=True)).to_be_disabled()

    # Fill in display name and enable Save button
    browser.get_by_placeholder("Enter display name here...").fill("SERVICE_ID_1")
    expect(
        browser.get_by_role("button", name="Save", exact=True)
    ).not_to_be_disabled()
    browser.get_by_role("button", name="Save", exact=True).click()
    browser.wait_for_timeout(1000)

    # Validate that the node was added
    node_with_text_1 = browser.locator("div.react-flow__node").filter(
        has_text="SERVICE_ID_1"
    )
    expect(node_with_text_1).to_have_count(1)
    browser.wait_for_timeout(1000)

    # Add another node to the topology
    browser.get_by_role("button", name="Add Node", exact=True).click()
    browser.get_by_placeholder("Enter service here...").fill("service_id_2")
    browser.get_by_placeholder("Enter display name here...").fill("SERVICE_ID_2")
    browser.get_by_role("button", name="Save", exact=True).click()
    browser.wait_for_timeout(1000)
    expect(browser.locator("div.react-flow__node")).to_have_count(2)
    browser.wait_for_timeout(1000)

    # Add a third node
    browser.get_by_role("button", name="Add Node", exact=True).click()
    browser.get_by_placeholder("Enter service here...").fill("service_id_1")
    browser.get_by_placeholder("Enter display name here...").fill("SERVICE_ID_3")
    browser.get_by_role("button", name="Save", exact=True).click()
    browser.wait_for_timeout(1000)
    expect(browser.locator("div.react-flow__node")).to_have_count(3)

    # Zoom out for better visibility
    zoom_out_button = browser.locator("button.react-flow__controls-zoomout")
    for _ in range(5):
        zoom_out_button.click()

    # Connect nodes by dragging source to target handles
    source_handle = browser.locator("div[data-id='1-1-right-source']")
    target_handle_2 = browser.locator("div[data-id='1-2-left-target']")
    target_handle_3 = browser.locator("div[data-id='1-3-left-target']")

    source_handle.drag_to(target_handle_2)
    source_handle.drag_to(target_handle_3)

    browser.wait_for_timeout(1000)

    # Validate edge connection
    edge_1_to_2 = browser.locator(
        "g.react-flow__edge[aria-label='Edge from 1 to 2']"
    )
    expect(edge_1_to_2).to_have_count(1)
    edge_1_to_3 = browser.locator(
        "g.react-flow__edge[aria-label='Edge from 1 to 3']"
    )
    expect(edge_1_to_3).to_have_count(1)

    # Delete edge
    edge_end = edge_1_to_2.locator("circle.react-flow__edgeupdater-target")
    edge_end.drag_to(browser.locator("body"), force=True)
    expect(
        browser.locator("g.react-flow__edge[aria-label='Edge from 1 to 2']")
    ).to_have_count(0)

    # Ensure remaining edges are intact
    expect(
        browser.locator("g.react-flow__edge[aria-label='Edge from 1 to 3']")
    ).to_have_count(1)
    browser.wait_for_timeout(2000)

    # Delete a node and ensure related edges are removed
    node_to_delete = browser.locator("div.react-flow__node").filter(
        has_text="SERVICE_ID_1"
    )
    node_to_delete.click()
    browser.wait_for_timeout(2000)
    browser.get_by_role("button", name="Delete Service", exact=True).click()
    browser.wait_for_timeout(1000)
    expect(
        browser.locator("div.react-flow__node").filter(has_text="SERVICE_ID_1")
    ).to_have_count(0)
    expect(
        browser.locator("g.react-flow__edge[aria-label='Edge from 1 to 3']")
    ).to_have_count(0)

    # Update node name and verify the change
    node_to_update = browser.locator("div.react-flow__node").filter(
        has_text="SERVICE_ID_2"
    )
    node_to_update.click()
    browser.get_by_role("button", name="Update Service", exact=True).click()

    input_field = browser.get_by_placeholder("Enter display name here...")
    input_field.clear()
    input_field.fill("UPDATED_SERVICE")
    browser.get_by_role("button", name="Update", exact=True).click()
    browser.wait_for_timeout(3000)
    expect(
        browser.locator("div.react-flow__node").filter(has_text="UPDATED_SERVICE")
    ).to_have_count(1)
