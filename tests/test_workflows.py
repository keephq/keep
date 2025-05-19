from datetime import datetime
from unittest.mock import patch

from keep.api.core.db import create_workflow_execution, get_workflow_execution
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.db.provider import Provider
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
    manager._run_workflow(
        workflow=workflow, workflow_execution_id=workflow_execution_id
    )
    results_db = get_workflow_execution(SINGLE_TENANT_UUID, workflow_execution_id)
    assert results_db.results.get("console-step") == ["hello world"]
    assert (
        results_db.results.get("keep-action")[0][0].get("name")
        == "Packloss for host in production !"
    )


workflow_postgres = (
    workflow_test
) = """workflow:
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
    - name: postgres-step
      provider:
        type: postgres
        config: "{{ providers.postgres-mock }}"
        with:
          query: select * from test_table
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


def test_workflow_postgres_results(db_session):
    workflow_db = Workflow(
        id="workflow_postgres",
        name="workflow_postgres",
        tenant_id=SINGLE_TENANT_UUID,
        description="workflow_postgres",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_test,
    )
    db_session.add(workflow_db)
    db_session.commit()

    from keep.providers.postgres_provider.postgres_provider import PostgresProvider

    postgres_secret_mock = "postgres_secret_mock"

    provider = Provider(
        id="postgres-mock",
        tenant_id=SINGLE_TENANT_UUID,
        name="postgres-mock",
        type="postgres",
        installed_by="test_user",
        installation_time=datetime.now(),
        configuration_key=postgres_secret_mock,
        validatedScopes=True,
        pulling_enabled=False,
    )
    db_session.add(provider)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)
    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {
            "authentication": {
                "username": "test",
                "password": "test",
                "host": "test",
            }
        }
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
        execution_number=12345,
        fingerprint="12345",
        event_id="12345",
        event_type="manual",
    )
    # mock postgres provider
    query_results = [
        [
            "ipaddresses.id.2026",
            {
                "id": 2026,
                "url": "https://some.com/api/ipam/ip-addresses/2026/",
                "vrf": None,
                "tags": [
                    {
                        "id": 1,
                        "url": "https://some.com/api/extras/tags/1/",
                        "name": "Keep",
                        "slug": "keep",
                        "color": "607d8b",
                        "display": "Keep",
                    },
                    {
                        "id": 1089,
                        "url": "https://some.com/api/extras/tags/1089/",
                        "name": "nmap",
                        "slug": "nmap",
                        "color": "66c8ee",
                        "display": "nmap",
                    },
                ],
                "family": {"label": "IPv4", "value": 4},
                "status": {"label": "Active", "value": "active"},
                "tenant": None,
                "address": "1.1.1.1/27",
                "created": "2023-11-20T12:04:25.987353Z",
                "display": "1.1.1.1/27",
                "comments": "",
                "dns_name": "",
                "nat_inside": None,
                "description": "",
                "nat_outside": [],
                "last_updated": "2024-11-22T16:22:24.035663Z",
                "custom_fields": {},
                "assigned_object": {
                    "id": 3277,
                    "url": "https://some.com/api/dcim/interfaces/3277/",
                    "name": "keep1",
                    "cable": None,
                    "device": {
                        "id": 821,
                        "url": "https://some.com/api/dcim/devices/821/",
                        "name": "KEEP",
                        "display": "KEEP",
                    },
                    "display": "keep1",
                    "_occupied": False,
                },
                "assigned_object_id": 3277,
                "assigned_object_type": "dcim.interface",
            },
            "2025-05-14T14:39:51.225677",
            "2025-05-14T14:39:51.225677",
        ]
    ]

    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {
            "authentication": {
                "username": "test",
                "password": "test",
                "host": "test",
            }
        }
        with patch.object(
            PostgresProvider,
            "_query",
            return_value=query_results,
        ):
            manager._run_workflow(
                workflow=workflow, workflow_execution_id=workflow_execution_id
            )
    results_db = get_workflow_execution(SINGLE_TENANT_UUID, workflow_execution_id)
    assert (
        results_db.results.get("keep-action")[0][0].get("name")
        == "Packloss for host in production !"
    )
