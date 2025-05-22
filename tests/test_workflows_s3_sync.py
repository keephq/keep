# Mock S3 workflow data for testing S3 sync functionality
from datetime import datetime

import pytz
from sqlmodel import col

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus, AlertSeverity
from keep.api.models.db.workflow import Workflow
from tests.fixtures.workflow_manager import (
    workflow_manager,
    wait_for_workflow_execution,
)


MOCK_S3_WORKFLOWS_YAMLS = [
    f"""workflow:
            id: workflow-{i}
            name: Workflow {i}
            description: Sync test workflow {i}
            triggers:
              - type: manual
            steps:
              - name: test-step
                provider:
                  type: console
                  with:
                    message: hello from workflow {i}
    """
    for i in range(1, 6)
]

# Modified version of workflow-3 to test updates
MODIFIED_WORKFLOW_YAML = """
workflow:
  id: workflow-3
  name: Workflow 3
  description: Sync test workflow 3 modified
  triggers:
    - type: manual
  steps:
    - name: test-step-modified
      provider:
        type: console
        with:
          message: test modified
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

    # Create a manual event to trigger the workflow
    current_time = datetime.now(tz=pytz.utc)
    manual_run_event = AlertDto(
        id="manual-run",
        name="sync-workflows-from-s3",
        status=AlertStatus.FIRING,
        severity=AlertSeverity.CRITICAL,
        lastReceived=current_time.isoformat(),
        source=["manual"],
        fingerprint="manual-run",
    )

    # Trigger workflow using workflow scheduler
    workflow_execution_id = workflow_manager.insert_events(
        SINGLE_TENANT_UUID, [manual_run_event]
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
    for i in range(1, 6):
        workflow_db = (
            db_session.query(Workflow).filter(Workflow.name == f"Workflow {i}").first()
        )
        assert workflow_db is not None
        assert workflow_db.name == f"Workflow {i}"
        assert workflow_db.revision == 1

    # Run again - should not change anything
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [manual_run_event])

    workflow_execution_2 = wait_for_workflow_execution(
        SINGLE_TENANT_UUID, "s3-workflow-sync", exclude_ids=[workflow_execution.id]
    )
    assert workflow_execution_2 is not None
    assert workflow_execution_2.status == "success"

    # Verify no changes in revisions
    for i in range(1, 6):
        workflow_db = (
            db_session.query(Workflow).filter(Workflow.name == f"Workflow {i}").first()
        )
        assert workflow_db.revision == 1

    # Modify workflow-3 and run again
    mock_s3_query.return_value = [MODIFIED_WORKFLOW_YAML]
    workflow_manager.insert_events(SINGLE_TENANT_UUID, [manual_run_event])

    workflow_execution = wait_for_workflow_execution(
        SINGLE_TENANT_UUID,
        "s3-workflow-sync",
        exclude_ids=[workflow_execution_id, workflow_execution_2.id],
    )

    # Verify only workflow-3 was updated
    for i in range(1, 6):
        workflow_db = (
            db_session.query(Workflow).filter(Workflow.name == f"Workflow {i}").first()
        )
        if i == 3:
            assert workflow_db.revision == 2
            assert workflow_db.name == "Workflow 3"
            assert workflow_db.description == "Sync test workflow 3 modified"
        else:
            assert workflow_db.revision == 1
            assert workflow_db.name == f"Workflow {i}"

    # Verify no duplicate workflows were created
    workflow_count = (
        db_session.query(Workflow)
        .filter(col(Workflow.description).like("%Sync Test%"))
        .count()
    )
    assert workflow_count == 5
