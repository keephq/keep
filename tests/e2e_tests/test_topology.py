import os
import sys

from playwright.sync_api import expect

from tests.e2e_tests.utils import init_e2e_test

# Importing utilities for test assertions and setup

# Setting Playwright to run in non-headless mode for debugging purposes
os.environ["PLAYWRIGHT_HEADLESS"] = "false"

# Base URL of the application under test
KEEP_UI_URL = "http://localhost:3000"


def test_topology_manual(browser):
    try:
        # Navigate to sign-in page
        # browser.goto(f"{KEEP_UI_URL}/signin")
        init_e2e_test(browser, next_url="/signin")
        browser.wait_for_timeout(3000)

        # Open the Service Topology page
        browser.get_by_role("link", name="Service Topology").hover()
        browser.get_by_role("link", name="Service Topology").click()
        browser.wait_for_timeout(5000)  # Added extra wait for page to fully load

        max_retries = 5
        retries = 0

        # Attempt to add a new service node, retrying in case of failure
        while retries <= max_retries:
            try:
                browser.get_by_role("button", name="Add Node", exact=True).click()
                browser.wait_for_timeout(2000)
                browser.get_by_placeholder("Enter service here...").fill("service_id_1")
                break
            except Exception:
                if retries == max_retries:
                    raise
                retries += 1
                browser.reload()
                browser.wait_for_timeout(2000)  # Added wait after reload

        # Ensure Save button is disabled when required fields are empty
        expect(browser.get_by_role("button", name="Save", exact=True)).to_be_disabled()

        # Fill in display name and enable Save button
        browser.get_by_placeholder("Enter display name here...").fill("SERVICE_ID_1")
        expect(
            browser.get_by_role("button", name="Save", exact=True)
        ).not_to_be_disabled()
        browser.get_by_role("button", name="Save", exact=True).click()
        browser.wait_for_timeout(2000)  # Increased wait time

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
        browser.wait_for_timeout(2000)  # Increased wait time
        expect(browser.locator("div.react-flow__node")).to_have_count(2)
        browser.wait_for_timeout(1000)

        # Add a third node
        browser.get_by_role("button", name="Add Node", exact=True).click()
        browser.get_by_placeholder("Enter service here...").fill(
            "service_id_3"
        )  # Changed ID to avoid potential conflicts
        browser.get_by_placeholder("Enter display name here...").fill("SERVICE_ID_3")
        browser.get_by_role("button", name="Save", exact=True).click()
        browser.wait_for_timeout(2000)  # Increased wait time
        expect(browser.locator("div.react-flow__node")).to_have_count(3)

        # Zoom out for better visibility
        zoom_out_button = browser.locator("button.react-flow__controls-zoomout")
        for _ in range(5):
            zoom_out_button.click()
            browser.wait_for_timeout(100)  # Small wait between zoom operations

        # Ensure the flow is stable before attempting to connect nodes
        browser.wait_for_timeout(2000)

        # Improved edge connection with retries
        def connect_nodes(source_handle, target_handle, edge_label, max_attempts=3):

            for attempt in range(max_attempts):
                try:
                    # Force visibility and ensure handles are in viewport
                    source_handle.scroll_into_view_if_needed()
                    target_handle.scroll_into_view_if_needed()

                    # Ensure the handles are visible before trying to drag
                    expect(source_handle).to_be_visible(timeout=5000)
                    expect(target_handle).to_be_visible(timeout=5000)

                    # Try the drag operation with force
                    source_handle.drag_to(target_handle, force=True)

                    # Wait and check if edge was created
                    browser.wait_for_timeout(1000)
                    edge = browser.locator(
                        f"g.react-flow__edge[aria-label='{edge_label}']"
                    )

                    # Try different wait strategies
                    for _ in range(10):
                        if edge.count() > 0:
                            return True
                        browser.wait_for_timeout(300)

                    # If we got here but still no edge, try a different approach
                    browser.mouse.move(
                        source_handle.bounding_box()["x"] + 5,
                        source_handle.bounding_box()["y"] + 5,
                    )
                    browser.mouse.down()
                    browser.wait_for_timeout(500)
                    browser.mouse.move(
                        target_handle.bounding_box()["x"] + 5,
                        target_handle.bounding_box()["y"] + 5,
                    )
                    browser.wait_for_timeout(500)
                    browser.mouse.up()
                    browser.wait_for_timeout(1000)

                    # Final check
                    if edge.count() > 0:
                        return True

                    # If still not created, continue to next attempt
                    browser.wait_for_timeout(1000)

                except Exception as e:
                    print(f"Attempt {attempt+1} failed: {str(e)}")
                    browser.wait_for_timeout(1000)

            return False

        # Define handles with stable selectors
        node_1 = browser.locator("div.react-flow__node-service").filter(has_text="SERVICE_ID_1")
        node_2 = browser.locator("div.react-flow__node-service").filter(has_text="SERVICE_ID_2")
        node_3 = browser.locator("div.react-flow__node-service").filter(has_text="SERVICE_ID_3")

        node_1_id = node_1.get_attribute('data-id')
        node_2_id = node_2.get_attribute('data-id')
        node_3_id = node_3.get_attribute('data-id')

        # Connect nodes by dragging source to target handles
        source_handle_1 = node_1.locator(f"div[data-id='1-{node_1_id}-right-source']")
        target_handle_2 = node_2.locator(f"div[data-id='1-{node_2_id}-left-target']")
        target_handle_3 = node_3.locator(f"div[data-id='1-{node_3_id}-left-target']")

        # Connect nodes with retry logic
        edge1_created = connect_nodes(
            source_handle_1, target_handle_2, f"Edge from {node_1_id} to {node_2_id}"
        )
        if not edge1_created:
            # Take diagnostic screenshots
            browser.screenshot(path="failed_edge1_creation.png")
            # Try alternative approach or raise clear error
            print("Failed to create edge from node 1 to node 2 after multiple attempts")

        edge2_created = connect_nodes(
            source_handle_1, target_handle_3, f"Edge from {node_1_id} to {node_3_id}"
        )
        if not edge2_created:
            # Take diagnostic screenshots
            browser.screenshot(path="failed_edge2_creation.png")
            # Try alternative approach or raise clear error
            print("Failed to create edge from node 1 to node 3 after multiple attempts")

        # Validate edge connections with more flexible assertions
        browser.wait_for_timeout(2000)
        edge_1_to_2 = browser.locator(f"g.react-flow__edge[aria-label='Edge from {node_1_id} to {node_2_id}']")
        expect(edge_1_to_2).to_have_count(1, timeout=10000)  # Increased timeout
        edge_1_to_3 = browser.locator(f"g.react-flow__edge[aria-label='Edge from {node_1_id} to {node_3_id}']")
        expect(edge_1_to_3).to_have_count(1, timeout=10000)  # Increased timeout

        # Continue with rest of the test...

        # Delete edge
        edge_end = edge_1_to_2.locator("circle.react-flow__edgeupdater-target")
        edge_end.scroll_into_view_if_needed()
        browser.wait_for_timeout(500)
        edge_end.drag_to(browser.locator("body"), force=True)
        browser.wait_for_timeout(1000)

        # Ensure edge was deleted with retry
        for _ in range(5):
            if (
                    browser.locator(
                        f"g.react-flow__edge[aria-label='Edge from {node_1_id} to {node_2_id}']"
                    ).count()
                    == 0
            ):
                if browser.locator("g.react-flow__edge").count() == 1:
                    break
            browser.wait_for_timeout(1000)

        expect(
            browser.locator(f"g.react-flow__edge[aria-label='Edge {node_1_id} to {node_2_id}']")
        ).to_have_count(0, timeout=5000)

        # Ensure remaining edges are intact
        expect(
            browser.locator(f"g.react-flow__edge[aria-label='Edge from {node_1_id} to {node_3_id}']")
        ).to_have_count(1, timeout=5000)
        browser.wait_for_timeout(2000)

        # Delete a node and ensure related edges are removed
        node_to_delete = browser.locator("div.react-flow__node").filter(
            has_text="SERVICE_ID_1"
        )
        node_to_delete.scroll_into_view_if_needed()
        node_to_delete.click()
        browser.wait_for_timeout(2000)
        browser.get_by_role("button", name="Delete Service", exact=True).click()
        browser.wait_for_timeout(2000)  # Increased wait time

        # Verify node deletion with retry
        for _ in range(5):
            if (
                browser.locator("div.react-flow__node")
                .filter(has_text="SERVICE_ID_1")
                .count()
                == 0
            ):
                break
            browser.wait_for_timeout(1000)

        expect(
            browser.locator("div.react-flow__node").filter(has_text="SERVICE_ID_1")
        ).to_have_count(0, timeout=5000)

        # Verify edge deletion with retry
        for _ in range(5):
            if (
                browser.locator(
                    f"g.react-flow__edge[aria-label='Edge from {node_1_id} to {node_3_id}']"
                ).count()
                == 0
            ):
                break
            browser.wait_for_timeout(1000)

        expect(
            browser.locator(f"g.react-flow__edge[aria-label='Edge from {node_1_id} to {node_3_id}']")
        ).to_have_count(0, timeout=5000)

        # Update node name and verify the change
        node_to_update = browser.locator("div.react-flow__node").filter(
            has_text="SERVICE_ID_2"
        )
        node_to_update.scroll_into_view_if_needed()
        node_to_update.click()
        browser.wait_for_timeout(1000)
        browser.get_by_role("button", name="Update Service", exact=True).click()

        input_field = browser.get_by_placeholder("Enter display name here...")
        input_field.clear()
        input_field.fill("UPDATED_SERVICE")
        browser.get_by_role("button", name="Update", exact=True).click()
        browser.wait_for_timeout(3000)

        # Verify update with retry
        for _ in range(5):
            if (
                browser.locator("div.react-flow__node")
                .filter(has_text="UPDATED_SERVICE")
                .count()
                > 0
            ):
                break
            browser.wait_for_timeout(1000)

        expect(
            browser.locator("div.react-flow__node").filter(has_text="UPDATED_SERVICE")
        ).to_have_count(1, timeout=5000)

    except Exception as e:
        # Enhanced error capturing
        print(f"Test failed with error: {str(e)}")

        # Capture screenshots and HTML dumps on test failure
        test_name = (
            "playwright_dump_"
            + os.path.basename(__file__)[:-3]
            + "_"
            + sys._getframe().f_code.co_name
        )
        browser.screenshot(path=test_name + ".png")

        # Capture additional diagnostic screenshot of current flow state
        browser.screenshot(path=test_name + "_flow_state.png")

        with open(test_name + ".html", "w") as f:
            f.write(browser.content())
        raise
