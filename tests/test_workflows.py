from datetime import datetime
from unittest.mock import patch

from keep.api.core.db import create_workflow_execution, get_workflow_execution
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.models.alert import AlertDto, AlertStatus
from keep.api.models.db.provider import Provider
from keep.api.models.db.workflow import Workflow
from keep.functions import cyaml
from keep.parser.parser import Parser
from keep.workflowmanager.workflowmanager import WorkflowManager
from tests.fixtures.workflow_manager import wait_for_workflow_execution

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


workflow_postgres = """workflow:
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


def test_workflow_enrichment_with_nested_results(db_session, create_alert):
    """Test that reproduces the bug where enrichment doesn't work with results[0][0] access pattern"""

    workflow_enrichment = """workflow:
  name: Enrichment Test
  description: Test enrichment with nested results access
  disabled: false
  triggers:
    - type: manual
  inputs: []
  consts: {}
  owners: []
  services: []
  steps:
    - name: mock-step
      provider:
        type: mock
        config: "{{ providers.mock-provider }}"
        with:
            enrich_alert:
                - key: originalSource
                  value: results[0][0].message.source
                - key: messageId
                  value: results[0][0].message._id
            command_output:
                -
                    - message:
                        source: "server-01"
                        level: "ERROR"
                        content: "Database connection failed"
                        _id: "msg123"
"""

    workflow_db = Workflow(
        id="enrichment-test",
        name="enrichment-test",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test enrichment with nested results",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_enrichment,
    )
    db_session.add(workflow_db)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)

    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {}
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
        execution_number=5678,
        fingerprint="5678",
        event_id="5678",
        event_type="manual",
    )

    alert_dto = AlertDto(id="1234", name="blabla", fingerprint="fpw1")
    # store it in the db cuz we need to query it
    dt = datetime.utcnow()
    create_alert(
        "fpw1",
        AlertStatus.FIRING,
        dt,
    )
    workflow.context_manager.set_event_context(alert_dto)
    manager._run_workflow(
        workflow=workflow, workflow_execution_id=workflow_execution_id
    )

    from keep.searchengine.searchengine import SearchEngine

    search_engine = SearchEngine(tenant_id=workflow.context_manager.tenant_id)
    alert = search_engine.search_alerts_by_cel(cel_query="fingerprint == 'fpw1'")
    # assert
    alert = alert[0]
    assert alert.fingerprint == "fpw1"
    assert alert.originalSource == "server-01"
    assert alert.messageId == "msg123"


def test_workflow_alert_creation(db_session):
    workflow_alert = """workflow:
  id: keep-alert-generator
  name: Keep Alert Generator
  description: Creates new alerts within the Keep system with customizable parameters and descriptions.
  triggers:
    - type: manual

  actions:
    - name: create-alert
      provider:
        type: keep
        with:
          alert:
            name: "Alert created from the workflow"
            description: "This alert was created from the create_alert_in_keep.yml example workflow."
            labels:
              environment: production
            severity: critical
            fingerprint: fingerprint-test
"""

    workflow_db = Workflow(
        id="alert-test",
        name="test-test",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test alert",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow_alert,
    )
    db_session.add(workflow_db)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)

    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {}
        workflow = parser.parse(
            SINGLE_TENANT_UUID,
            workflow_yaml,
            workflow_db_id=workflow_db.id,
            workflow_revision=workflow_db.revision,
            is_test=workflow_db.is_test,
        )[0]

    from freezegun import freeze_time

    with freeze_time("2024-02-01 10:00:00"):
        manager = WorkflowManager.get_instance()
        workflow_execution_id = create_workflow_execution(
            workflow_id=workflow_db.id,
            workflow_revision=workflow_db.revision,
            tenant_id=SINGLE_TENANT_UUID,
            triggered_by="test executor",
            execution_number=11234,
            event_type="manual",
        )
        manager._run_workflow(
            workflow=workflow, workflow_execution_id=workflow_execution_id
        )

        from keep.searchengine.searchengine import SearchEngine

        search_engine = SearchEngine(tenant_id=workflow.context_manager.tenant_id)
        alert = search_engine.search_alerts_by_cel(
            cel_query="fingerprint == 'fingerprint-test'"
        )
        # assert
        alert = alert[0]
        assert alert.fingerprint == "fingerprint-test"
        assert alert.lastReceived.startswith("2024-02-01T10:00:00")

    with freeze_time("2024-02-15 10:00:00"):
        manager = WorkflowManager.get_instance()
        workflow_execution_id = create_workflow_execution(
            workflow_id=workflow_db.id,
            workflow_revision=workflow_db.revision,
            tenant_id=SINGLE_TENANT_UUID,
            triggered_by="test executor",
            execution_number=11235,
            event_type="manual",
        )
        manager._run_workflow(
            workflow=workflow, workflow_execution_id=workflow_execution_id
        )

        from keep.searchengine.searchengine import SearchEngine

        search_engine = SearchEngine(tenant_id=workflow.context_manager.tenant_id)
        alert = search_engine.search_alerts_by_cel(
            cel_query="fingerprint == 'fingerprint-test'"
        )
        # assert
        alert = alert[0]
        assert alert.fingerprint == "fingerprint-test"
        assert alert.lastReceived.startswith("2024-02-15T10:00:00")


def test_workflow_python(db_session):
    workflow = """workflow:
  id: random-python
  name: random-python
  triggers:
    - type: manual
  steps:
    - name: random
      provider:
        config: "{{ providers.default-python }}"
        type: python
        with:
          imports: random
          code: |-
            random.randint(1, 100)
  actions:
    - name: random-print
      provider:
        type: console
        with:
          message: "Random number: {{ steps.random.results }}"
"""
    workflow_db = Workflow(
        id="test-python",
        name="test-python",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test python",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow,
    )
    db_session.add(workflow_db)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)

    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {}
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
        execution_number=11234,
        event_type="manual",
    )
    manager._run_workflow(
        workflow=workflow, workflow_execution_id=workflow_execution_id
    )

    wf_execution = get_workflow_execution(SINGLE_TENANT_UUID, workflow_execution_id)
    assert "Random number:" in wf_execution.results.get("random-print")[0]


def test_workflow_bash(db_session):
    workflow = """workflow:
  id: random-bash
  name: random-bash
  triggers:
    - type: manual
  steps:
    - name: bash-step
      provider:
        type: bash
        with:
          command: echo -n 5
  actions:
    - name: bash-if
      if: "{{ steps.bash-step.results.stdout }} == '5' "
      provider:
        type: console
        with:
          message: "It is actually 5!"
"""
    workflow_db = Workflow(
        id="test-bash",
        name="test-bash",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test bash",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow,
    )
    db_session.add(workflow_db)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)

    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {}
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
        execution_number=11234,
        event_type="manual",
    )
    manager._run_workflow(
        workflow=workflow, workflow_execution_id=workflow_execution_id
    )

    wf_execution = get_workflow_execution(SINGLE_TENANT_UUID, workflow_execution_id)
    assert wf_execution.results.get("bash-step")[0].get("stdout") == "5"


def test_workflow_bash_python(db_session):
    workflow = """workflow:
  id: random-bash
  name: random-bash
  triggers:
    - type: manual
  steps:
    - name: bash-step
      provider:
        type: bash
        with:
          shell: true
          command: |
            cat << 'EOF' > script.py
            import random
            print(random.randint(1, 100))
            EOF
            python script.py && rm script.py
"""
    workflow_db = Workflow(
        id="test-bash",
        name="test-bash",
        tenant_id=SINGLE_TENANT_UUID,
        description="Test bash",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow,
    )
    db_session.add(workflow_db)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)

    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {}
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
        execution_number=11234,
        event_type="manual",
    )
    manager._run_workflow(
        workflow=workflow, workflow_execution_id=workflow_execution_id
    )

    wf_execution = get_workflow_execution(SINGLE_TENANT_UUID, workflow_execution_id)
    assert wf_execution.results.get("bash-step")[0].get("return_code") == 0


@patch(
    "keep.providers.postgres_provider.postgres_provider.PostgresProvider._notify",
    return_value=None,
)
@patch(
    "keep.providers.postgres_provider.postgres_provider.PostgresProvider.validate_config"
)
@patch("keep.step.step.StepError")
@patch("keep.api.tasks.process_event_task.process_event")
def test_workflow_keep_notify_after_another_foreach(
    mock_process_event,
    mock_step_error,
    mock_postgres_validate_config,
    mock_postgres_notify,
    db_session,
):
    workflow = """workflow:
  id: keep-notify-after-foreach
  name: Keep Notify After Foreach
  triggers:
    - type: manual
  steps:
    - name: python-step
      provider:
        type: python
        with:
          code: '["item1", "item2", "item3"]'
  actions:
    - name: add-to-db
      foreach: "{{ steps.python-step.results }}"
      provider:
        type: postgres
        with:
          query: "INSERT INTO test_table (name) VALUES ('{{ foreach.value }}')"
    - name: create-alerts
      foreach: "{{ steps.python-step.results }}"
      provider:
        type: keep
        with:
          alert:
            name: "{{ foreach.value }}"
            description: "This alert was created from the foreach step."
            severity: critical
            fingerprint: "{{ foreach.value }}"
"""

    workflow_db = Workflow(
        id="keep-notify-after-foreach",
        name="Keep Notify After Foreach",
        tenant_id=SINGLE_TENANT_UUID,
        description="Keep Notify After Foreach",
        created_by="test@keephq.dev",
        interval=0,
        workflow_raw=workflow,
        last_updated=datetime.now(),
    )

    db_session.add(workflow_db)
    db_session.commit()

    parser = Parser()
    workflow_yaml = cyaml.safe_load(workflow_db.workflow_raw)

    with patch(
        "keep.secretmanager.secretmanagerfactory.SecretManagerFactory.get_secret_manager"
    ) as mock_secret_manager:
        mock_secret_manager.return_value.read_secret.return_value = {}
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
        execution_number=11234,
        event_type="manual",
    )
    manager._run_workflow(
        workflow=workflow, workflow_execution_id=workflow_execution_id
    )

    assert mock_step_error.call_count == 0
