from keep.api.core.db import create_workflow_execution, get_workflow_execution
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.workflow import Workflow
from keep.functions import cyaml
from keep.parser.parser import Parser
from keep.workflowmanager.workflowmanager import WorkflowManager

workflow_test = """workflow:
  name: Alert Simple
  description: Alert Simple
  disabled: false
  triggers:
    - type: manual
  inputs: []
  consts: {}
  owners: []
  services: []
  steps:
    - name: console-step
      provider:
        type: console
        with:
          message: hello world
  actions:
    - name: keep-action
      provider:
        type: keep
        with:
          alert:
            name: Packloss for host in production !
            description: This host reports packet loss and is registered as production in DB
            severity: critical
"""


def test_workflow(
    db_session,
):

    workflow_db = Workflow(
        id="alert-time-check",
        name="alert-time-check",
        tenant_id=SINGLE_TENANT_UUID,
        description="Handle alerts based on startedAt timestamp",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_test,
    )
    db_session.add(workflow_db)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)
    workflow = parser.parse(
        SINGLE_TENANT_UUID,
        workflow_yaml,
        workflow_db_id=workflow_db.id,
        workflow_revision=workflow_db.revision,
        is_test=workflow_db.is_test,
    )[0]
    manager = WorkflowManager.get_instance()

    workflow_execution_id = create_workflow_execution(
        workflow_id=workflow_db.id,
        workflow_revision=workflow_db.revision,
        tenant_id=SINGLE_TENANT_UUID,
        triggered_by="test executor",
        execution_number=1234,
        fingerprint="1234",
        event_id="1234",
        event_type="manual",
    )
    results = manager._run_workflow(
        workflow=workflow, workflow_execution_id=workflow_execution_id
    )
    results_db = get_workflow_execution(SINGLE_TENANT_UUID, workflow_execution_id)
    assert results_db.results == results
