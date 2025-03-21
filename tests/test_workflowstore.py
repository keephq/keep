from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import Workflow
from keep.workflowmanager.workflowstore import WorkflowStore

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
