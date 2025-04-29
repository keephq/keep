from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import Workflow
from keep.workflowmanager.workflowstore import WorkflowStore
from keep.api.core.db import get_all_provisioned_workflows
from tests.fixtures.client import test_app  # noqa
import pytest

VALID_WORKFLOW = """
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
    assert len(first_provisioned) == 1  # There are 1 workflow in workflows_3 directory
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
