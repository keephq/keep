from datetime import datetime, timezone
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import (
    Workflow,
    WorkflowExecution,
    WorkflowExecutionLog,
)
from keep.workflowmanager.workflowstore import WorkflowStore
from keep.api.core.db import get_all_provisioned_workflows
from tests.fixtures.client import test_app  # noqa
import pytest
import time
from uuid import uuid4

VALID_WORKFLOW = """
workflow:
  id: retrieve-cloudwatch-logs
  name: Retrieve CloudWatch Logs
  description: Retrieve CloudWatch Logs
  triggers:
    - type: manual
  steps:
    - name: cw-logs
      provider:
        config: "{{ providers.cloudwatch }}"
        type: cloudwatch
        with:
          log_groups: 
            - "meow_logs"
          query: "fields @message | sort @timestamp desc | limit 20"
          hours: 4000
          remove_ptr_from_results: true
"""

INVALID_WORKFLOW = """
workflow:
  id: retrieve-cloudwatch-logs
  name: Retrieve CloudWatch Logs
  description: Retrieve CloudWatch Logs
  triggers:
    - type: manual
  steps:
    - name: cw-logs
      provider:
        config: "{{ providers.cloudwatch }}"
        type: cloudwatch
        with:
          log_groups: 
            - "meow_logs"
          query: "fields @message | sort @timestamp desc | limit 20"
          hours: 4000
          remove_ptr_from_results: true
  actions:
    - name: print-logs
      if: keep.len({{ steps.cw-logs.results }}) > 0
      type: print
      with:
        message: "{{ steps.cw-logs.results }}"
"""


def is_workflow_raw_equal(a, b):
    return a.replace(" ", "").replace("\n", "") == b.replace(" ", "").replace("\n", "")


def test_get_workflow_meta_data_3832():
    valid_workflow = Workflow(
        id="valid-workflow",
        name="valid-workflow",
        tenant_id=SINGLE_TENANT_UUID,
        description="some stuff for unit testing",
        created_by="vovka.morkovka@keephq.dev",
        interval=0,
        workflow_raw=VALID_WORKFLOW,
    )

    workflowstore = WorkflowStore()

    providers_dto, triggers = workflowstore.get_workflow_meta_data(
        tenant_id=SINGLE_TENANT_UUID,
        workflow=valid_workflow,
        installed_providers_by_type={},
    )

    assert len(triggers) == 1
    assert triggers[0] == {"type": "manual"}

    assert len(providers_dto) == 1
    assert providers_dto[0].type == "cloudwatch"

    # And now let's check partially misconfigured workflow

    invalid_workflow = Workflow(
        id="invalid-workflow",
        name="invalid-workflow",
        tenant_id=SINGLE_TENANT_UUID,
        description="some stuff for unit testing",
        created_by="vovka.morkovka@keephq.dev",
        interval=0,
        workflow_raw=INVALID_WORKFLOW,
    )

    workflowstore = WorkflowStore()

    providers_dto, triggers = workflowstore.get_workflow_meta_data(
        tenant_id=SINGLE_TENANT_UUID,
        workflow=invalid_workflow,
        installed_providers_by_type={},
    )

    assert len(triggers) == 1
    assert triggers[0] == {"type": "manual"}

    assert len(providers_dto) == 1
    assert providers_dto[0].type == "cloudwatch"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_WORKFLOWS_DIRECTORY": "./tests/provision/workflows_3",
        },
    ],
    indirect=True,
)
def test_provision_workflows_no_duplicates(monkeypatch, db_session, test_app):
    """Test that workflows are not provisioned twice when provision_workflows is called multiple times."""
    # First provisioning
    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after first provisioning
    first_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(first_provisioned) == 1  # There is 1 workflow in workflows_3 directory
    first_workflow_ids = {w.id for w in first_provisioned}

    # Second provisioning
    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after second provisioning
    second_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(second_provisioned) == 1  # Should still be 1 workflow
    second_workflow_ids = {w.id for w in second_provisioned}

    # Verify the workflows are the same
    assert first_workflow_ids == second_workflow_ids

    # Verify each workflow's content is unchanged
    for first_w in first_provisioned:
        second_w = next(w for w in second_provisioned if w.id == first_w.id)
        assert first_w.name == second_w.name
        assert first_w.workflow_raw == second_w.workflow_raw
        assert first_w.provisioned_file == second_w.provisioned_file


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_WORKFLOWS_DIRECTORY": "./tests/provision/workflows_3",
        },
    ],
    indirect=True,
)
def test_unprovision_workflows(monkeypatch, db_session, test_app):
    """Test that provisioned workflows are deleted when they are no longer provisioned via env or dir."""
    # First provisioning
    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after first provisioning
    first_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(first_provisioned) == 1  # There is 1 workflow in workflows_3 directory

    monkeypatch.delenv("KEEP_WORKFLOWS_DIRECTORY")
    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after second provisioning
    second_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(second_provisioned) == 0


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
        },
    ],
    indirect=True,
)
def test_invalid_workflows_dir(monkeypatch, db_session, test_app):
    """Test exception is raised when invalid dir is passed as KEEP_WORKFLOWS_DIRECTORY."""

    monkeypatch.setenv("KEEP_WORKFLOWS_DIRECTORY", "./tests/provision/workflows_404")

    # First provisioning
    with pytest.raises(FileNotFoundError):
        WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after first provisioning
    provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(provisioned) == 0  # No workflows has been provisioned


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_WORKFLOWS_DIRECTORY": "./tests/provision/workflows_1",
        },
    ],
    indirect=True,
)
def test_change_workflow_provision_method(monkeypatch, db_session, test_app):
    """Test that provisioned workflows are deleted when they are no longer provisioned via env or dir."""
    # First provisioning
    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after first provisioning
    first_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(first_provisioned) == 3  # There is 3 workflows in workflows_1 directory

    # Provision from env instead of dir
    monkeypatch.delenv("KEEP_WORKFLOWS_DIRECTORY")
    monkeypatch.setenv("KEEP_WORKFLOW", VALID_WORKFLOW)

    WorkflowStore.provision_workflows(SINGLE_TENANT_UUID)

    # Get workflows after second provisioning
    second_provisioned = get_all_provisioned_workflows(SINGLE_TENANT_UUID)
    assert len(second_provisioned) == 1
    assert second_provisioned[0].name == "Retrieve CloudWatch Logs"
    assert is_workflow_raw_equal(second_provisioned[0].workflow_raw, VALID_WORKFLOW)


def test_workflow_execution_large_results_many_logs_performance(db_session):
    """
    Performance test for the OOM fix: Tests the scenario that caused the original issue:
    - Large workflow results (~500KB)
    - Many logs (~1000 entries)

    This test verifies that:
    1. WorkflowStore.get_workflow_execution_with_logs handles this scenario without OOM
    2. Performance is reasonable (should complete in milliseconds, not seconds)
    3. Memory usage is controlled by not duplicating large results across log rows
    """

    workflowstore = WorkflowStore()

    # Create a large results object (~500KB) similar to what caused the OOM
    large_results = {
        "step1": {
            "data": "x" * 100000,  # 100KB of data
            "items": [
                {"id": i, "value": "data" * 100} for i in range(1000)
            ],  # ~400KB more
        },
        "step2": {
            "processed_items": [
                f"item_{i}_processed_with_long_description" for i in range(5000)
            ],
        },
    }

    # Verify our test data is approximately the right size
    import json

    results_size = len(json.dumps(large_results).encode("utf-8"))
    assert results_size > 400000  # Should be > 400KB
    print(f"Test results size: {results_size / 1024:.1f} KB")

    # Create a workflow execution with large results
    execution_id = str(uuid4())
    workflow_execution = WorkflowExecution(
        id=execution_id,
        workflow_id="perf-test-workflow",
        workflow_revision=1,
        tenant_id=SINGLE_TENANT_UUID,
        started=datetime.now(tz=timezone.utc),
        triggered_by="performance-test",
        execution_number=1,
        status="success",
        error=None,
        execution_time=10,
        results=large_results,  # Large results that caused the OOM
        is_test_run=False,
    )
    db_session.add(workflow_execution)
    db_session.flush()  # Get the ID

    # Create many logs (~1000) - this is what caused the cartesian product issue
    logs_to_create = 1000
    log_entries = []
    for i in range(logs_to_create):
        log_entry = WorkflowExecutionLog(
            workflow_execution_id=execution_id,
            timestamp=datetime.now(tz=timezone.utc),
            message=f"Log message {i}: Processing step with detailed information about execution progress",
            context={
                "step": i,
                "status": "processing",
                "details": f"Additional context for step {i}",
            },
        )
        log_entries.append(log_entry)

    db_session.add_all(log_entries)
    db_session.commit()

    print(
        f"Created workflow execution with {results_size / 1024:.1f} KB results and {logs_to_create} log entries"
    )

    # This should NOT cause OOM and should be fast
    start_time = time.time_ns()
    execution_with_logs, logs = workflowstore.get_workflow_execution_with_logs(
        tenant_id=SINGLE_TENANT_UUID, workflow_execution_id=execution_id
    )
    end_time = time.time_ns()

    query_time = (end_time - start_time) / 1e6
    print(f"get_workflow_execution_with_logs took {query_time:.2f} milliseconds")

    # Verify the data is correct
    assert execution_with_logs is not None
    assert execution_with_logs.id == execution_id
    assert execution_with_logs.results == large_results  # Large results preserved
    assert len(logs) == logs_to_create  # All logs returned

    # Verify logs have correct structure
    for i, log in enumerate(logs):
        assert log.workflow_execution_id == execution_id
        assert f"Log message {i}" in log.message
        assert log.context.get("step") == i

    # Performance assertion: Should complete in reasonable time (under 500ms)
    # The old implementation would either OOM or take much longer due to massive result duplication
    assert (
        query_time < 500
    ), f"Query took too long: {query_time:.2f}ms. Expected < 500ms"

    # Test the original function to ensure it still works (but without accessing logs)
    start_time = time.time_ns()
    execution_only = workflowstore.get_workflow_execution(
        tenant_id=SINGLE_TENANT_UUID, workflow_execution_id=execution_id
    )
    end_time = time.time_ns()

    query_time_original = (end_time - start_time) / 1e6
    print(f"get_workflow_execution took {query_time_original:.2f} milliseconds")

    # Verify execution data is identical
    assert execution_only is not None
    assert execution_only.id == execution_with_logs.id
    assert execution_only.results == execution_with_logs.results
    assert execution_only.status == execution_with_logs.status


def test_get_all_workflows_with_last_execution_no_dummy_workflow(db_session):
    """
    Test that get_all_workflows_with_last_execution does not return dummy workflows.
    """
    from keep.api.core.db import get_or_create_dummy_workflow
    from keep.api.models.db.workflow import get_dummy_workflow_id

    workflowstore = WorkflowStore()

    # Create some regular workflows
    regular_workflow_1 = Workflow(
        id="regular-workflow-1",
        name="Regular Workflow 1",
        tenant_id=SINGLE_TENANT_UUID,
        description="A regular workflow for testing",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=VALID_WORKFLOW,
        last_updated=datetime.now(tz=timezone.utc),
    )

    regular_workflow_2 = Workflow(
        id="regular-workflow-2",
        name="Regular Workflow 2",
        tenant_id=SINGLE_TENANT_UUID,
        description="Another regular workflow for testing",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=VALID_WORKFLOW,
        last_updated=datetime.now(tz=timezone.utc),
    )

    # Add regular workflows to database
    db_session.add(regular_workflow_1)
    db_session.add(regular_workflow_2)
    db_session.commit()

    # Create a dummy workflow
    dummy_workflow = get_or_create_dummy_workflow(SINGLE_TENANT_UUID, db_session)
    dummy_workflow_id = get_dummy_workflow_id(SINGLE_TENANT_UUID)

    # Debug: Print dummy workflow info
    print(f"Dummy workflow ID: {dummy_workflow_id}")
    print(f"Dummy workflow name: {dummy_workflow.name}")
    print(f"Dummy workflow tenant_id: {dummy_workflow.tenant_id}")

    # Verify dummy workflow was created
    assert dummy_workflow is not None
    assert dummy_workflow.id == dummy_workflow_id
    assert "Dummy Workflow" in dummy_workflow.name

    # Get all workflows with last execution
    workflows, count = workflowstore.get_all_workflows_with_last_execution(
        tenant_id=SINGLE_TENANT_UUID,
        # db_session fixture creates two test workflows, we want to exclude them
        cel="!(name in ['test-id-1', 'test-id-2'])",
    )

    # Verify that we get the regular workflows but not the dummy workflow
    workflow_ids = [w["workflow"].id for w in workflows]
    workflow_names = [w["workflow"].name for w in workflows]

    # Should contain regular workflows
    assert "regular-workflow-1" in workflow_ids
    assert "regular-workflow-2" in workflow_ids
    assert "Regular Workflow 1" in workflow_names
    assert "Regular Workflow 2" in workflow_names

    # Should NOT contain dummy workflow
    assert dummy_workflow_id not in workflow_ids
    assert not any("Dummy Workflow" in name for name in workflow_names)

    # Count should reflect only regular workflows
    assert count == 2
    assert len(workflows) == 2
