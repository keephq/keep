# Mock S3 workflow data for testing S3 sync functionality
from datetime import datetime

import pytz

from keep.api.core.db import get_all_workflows
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus, AlertSeverity
from keep.api.models.db.workflow import Workflow
from keep.functions import cyaml
from tests.fixtures.workflow_manager import (
    workflow_manager,
    wait_for_workflow_execution,
)


MOCK_S3_WORKFLOWS_YAMLS = [
    f"""
    workflow:
        id: workflow-{i}
        name: Workflow {i}
        description: Sync test workflow {i}
        disabled: false
        triggers:
            - type: manual
        inputs: []
        consts: {{}}
        owners: []
        services: []
        steps:
            - name: test-step
              provider:
                  type: console
                  config: "{{ providers.default-console }}"
                  with:
                    message: hello from workflow {i}
        actions: []
    """
    for i in range(1, 6)
]

# Modified version of workflow-3 to test updates
MODIFIED_WORKFLOW_YAML = """
workflow:
  id: workflow-3
  name: Workflow 3
  description: Sync test workflow 3 modified
  disabled: false
  triggers:
    - type: manual
  inputs: []
  consts: {}
  owners: []
  services: []
  steps:
    - name: test-step-modified
      provider:
        type: console
        config: "{{ providers.default-console }}"
        with:
          message: test modified
  actions: []
"""


# S3 sync workflow definition
S3_SYNC_WORKFLOW_DEFINITION = """
workflow:
  id: s3-workflow-sync
  name: S3 Workflow Sync
  description: Synchronizes Keep workflows from S3 bucket storage
  disabled: false
  triggers:
    - type: manual
    - type: alert
      cel: name == "sync-workflows-from-s3"
  inputs: []
  consts: {}
  owners: []
  services: []
  steps:
    - name: s3-dump
      provider:
        type: s3
        config: "{{ providers.s3 }}"
        with:
          bucket: keep-workflows
  actions:
    - name: update
      foreach: "{{ steps.s3-dump.results }}"
      provider:
        type: keep
        config: "{{ providers.default-keep }}"
        with:
          workflow_to_update_yaml: raw_render_without_execution({{ foreach.value }})
"""


def assert_workflow_yaml(a: str, b: str):
    a_yaml = cyaml.safe_load(a)
    if "workflow" in a_yaml:
        a_yaml = a_yaml.pop("workflow")
    b_yaml = cyaml.safe_load(b)
    if "workflow" in b_yaml:
        b_yaml = b_yaml.pop("workflow")
    assert a_yaml == b_yaml


def get_manual_run_event(name: str):
    current_time = datetime.now(tz=pytz.utc)
    manual_run_event = AlertDto(
        id="manual-run",
        name=name,
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=current_time.isoformat(),
        source=["manual"],
        fingerprint="manual-run",
    )
    return manual_run_event


def test_s3_workflow_sync_manual_trigger(db_session, workflow_manager, mocker):
    """Test the S3 workflow sync functionality using manual trigger."""
    # Create the sync workflow
    sync_workflow = Workflow(
        id="s3-workflow-sync",
        name="s3-workflow-sync",
        tenant_id=SINGLE_TENANT_UUID,
        description="Synchronizes Keep workflows from S3 bucket storage",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=S3_SYNC_WORKFLOW_DEFINITION,
        last_updated=datetime.now(),
    )
    db_session.add(sync_workflow)
    db_session.commit()

    # Mock S3 provider to return our mock workflows
    mock_s3_validate_config = mocker.patch(
        "keep.providers.s3_provider.s3_provider.S3Provider.validate_config"
    )
    mock_s3_validate_config.return_value = True
    mock_s3_query = mocker.patch(
        "keep.providers.s3_provider.s3_provider.S3Provider._query"
    )
    mock_s3_query.return_value = MOCK_S3_WORKFLOWS_YAMLS

    # Trigger workflow using workflow scheduler
    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [get_manual_run_event("sync-workflows-from-s3")]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    # Wait for workflow execution to complete
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "s3-workflow-sync"
    )

    # Verify workflow execution
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Verify all workflows were created with version 1
    workflows = [
        w
        for w in get_all_workflows(SINGLE_TENANT_UUID)
        if w.description.startswith("Sync test workflow")
    ]
    for i, workflow_yaml in enumerate(MOCK_S3_WORKFLOWS_YAMLS):
        workflow = next((w for w in workflows if w.name == f"Workflow {i + 1}"), None)
        assert workflow is not None
        assert_workflow_yaml(workflow.workflow_raw, workflow_yaml)
        assert workflow.revision == 1

    # Run again - should not change anything
    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [get_manual_run_event("sync-workflows-from-s3")]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    workflow_execution_2 = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "s3-workflow-sync", exclude_ids=[workflow_execution.id]
    )
    assert workflow_execution_2 is not None
    assert workflow_execution_2.status == "success"

    # Verify no changes in revisions
    workflows = [
        w
        for w in get_all_workflows(SINGLE_TENANT_UUID)
        if w.description.startswith("Sync test workflow")
    ]

    for i, workflow_yaml in enumerate(MOCK_S3_WORKFLOWS_YAMLS):
        workflow_db = next(
            (w for w in workflows if w.name == f"Workflow {i + 1}"), None
        )
        assert workflow_db is not None
        assert_workflow_yaml(workflow_db.workflow_raw, workflow_yaml)
        assert workflow_db.revision == 1

    # Modify workflow-3 and run again
    mock_s3_query.return_value = [MODIFIED_WORKFLOW_YAML]
    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [get_manual_run_event("sync-workflows-from-s3")]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1
    workflow_execution_3 = wait_for_workflow_execution(
        SINGLE_TENANT_UUID,
        "s3-workflow-sync",
        exclude_ids=[workflow_execution.id, workflow_execution_2.id],
    )
    assert workflow_execution_3 is not None
    assert workflow_execution_3.status == "success"

    latest_workflows = [
        w
        for w in get_all_workflows(SINGLE_TENANT_UUID)
        if w.description.startswith("Sync test workflow")
    ]
    # Verify no duplicate workflows were created
    assert len(latest_workflows) == 5

    # Verify only workflow-3 was updated
    for i, workflow_yaml in enumerate(MOCK_S3_WORKFLOWS_YAMLS):
        workflow_db = next(
            (w for w in latest_workflows if w.name == f"Workflow {i + 1}"), None
        )
        assert workflow_db is not None
        if i == 2:
            assert workflow_db.revision == 2
            assert_workflow_yaml(workflow_db.workflow_raw, MODIFIED_WORKFLOW_YAML)
        else:
            assert workflow_db.revision == 1
            assert_workflow_yaml(workflow_db.workflow_raw, workflow_yaml)


def test_workflow_update_from_workflow(db_session, workflow_manager, mocker):
    """Test that workflow revision is incremented when content changes."""
    # Create initial workflow
    initial_workflow_yaml = """
    workflow:
        id: sync-test-workflow
        name: Sync Test Workflow
        description: Initial workflow
        disabled: false
        steps:
            - name: test-step
              provider:
                  type: console
                  config: "{{ providers.default-console }}"
                  with:
                    message: initial message
    """

    # Add debug logging to print initial workflow state
    print(f"Initial workflow state: {initial_workflow_yaml}")

    # Update workflow with modified content
    modified_workflow_yaml = """
    workflow:
        id: sync-test-workflow
        name: Sync Test Workflow
        description: Modified workflow
        disabled: false
        steps:
            - name: test-step-modified
              provider:
                  type: console
                  config: "{{ providers.default-console }}"
                  with:
                    message: modified message
    """

    # Mock S3 provider to return our modified workflow
    mock_s3_validate_config = mocker.patch(
        "keep.providers.s3_provider.s3_provider.S3Provider.validate_config"
    )
    mock_s3_validate_config.return_value = True
    mock_s3_query = mocker.patch(
        "keep.providers.s3_provider.s3_provider.S3Provider._query"
    )
    mock_s3_query.return_value = [initial_workflow_yaml]

    # Create the sync workflow
    sync_workflow = Workflow(
        id="s3-workflow-sync",
        name="s3-workflow-sync",
        tenant_id=SINGLE_TENANT_UUID,
        description="Synchronizes Keep workflows from S3 bucket storage",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=S3_SYNC_WORKFLOW_DEFINITION,
        last_updated=datetime.now(),
    )
    db_session.add(sync_workflow)
    db_session.commit()

    # Trigger workflow using workflow scheduler
    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [get_manual_run_event("sync-workflows-from-s3")]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    # Wait for workflow execution to complete
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "s3-workflow-sync"
    )

    # Verify workflow execution
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Update workflow with modified content
    mock_s3_query.return_value = [modified_workflow_yaml]

    # Trigger workflow using workflow scheduler
    workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [get_manual_run_event("sync-workflows-from-s3")]
    )
    assert len(workflow_manager.scheduler.workflows_to_run) == 1

    # Wait for workflow execution to complete
    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "s3-workflow-sync"
    )

    # Verify workflow execution
    assert workflow_execution is not None
    assert workflow_execution.status == "success"

    # Verify workflow was updated and revision incremented
    updated_workflow = next(
        (
            w
            for w in get_all_workflows(SINGLE_TENANT_UUID)
            if w.name == "Sync Test Workflow"
        ),
        None,
    )
    assert updated_workflow is not None

    assert_workflow_yaml(updated_workflow.workflow_raw, modified_workflow_yaml)
    assert updated_workflow.revision == 2
