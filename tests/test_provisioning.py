import asyncio
import importlib
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.fixtures.client import client, setup_api_key, test_app  # noqa

# Mock data for workflows
MOCK_WORKFLOW_ID = "123e4567-e89b-12d3-a456-426614174000"
MOCK_PROVISIONED_WORKFLOW = {
    "id": MOCK_WORKFLOW_ID,
    "name": "Test Workflow",
    "description": "A provisioned test workflow",
    "provisioned": True,
}


# Test for deleting a provisioned workflow
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
def test_provisioned_workflows(db_session, client, test_app):
    response = client.get("/workflows", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 3 workflows and 3 provisioned workflows
    workflows = response.json()
    provisioned_workflows = [w for w in workflows if w.get("provisioned")]
    assert len(provisioned_workflows) == 3


# Test for deleting a provisioned workflow
@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_WORKFLOWS_DIRECTORY": "./tests/provision/workflows_2",
        },
    ],
    indirect=True,
)
def test_provisioned_workflows_2(db_session, client, test_app):
    response = client.get("/workflows", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 3 workflows and 3 provisioned workflows
    workflows = response.json()
    provisioned_workflows = [w for w in workflows if w.get("provisioned")]
    assert len(provisioned_workflows) == 2


# Test for deleting a provisioned workflow
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
def test_delete_provisioned_workflow(db_session, client, test_app):
    response = client.get("/workflows", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 3 workflows and 3 provisioned workflows
    workflows = response.json()
    provisioned_workflows = [w for w in workflows if w.get("provisioned")]
    workflow_id = provisioned_workflows[0].get("id")
    response = client.delete(
        f"/workflows/{workflow_id}", headers={"x-api-key": "someapikey"}
    )
    # can't delete a provisioned workflow
    assert response.status_code == 403
    assert response.json() == {"detail": "Cannot delete a provisioned workflow"}


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
def test_update_provisioned_workflow(db_session, client, test_app):
    response = client.get("/workflows", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 3 workflows and 3 provisioned workflows
    workflows = response.json()
    provisioned_workflows = [w for w in workflows if w.get("provisioned")]
    workflow_id = provisioned_workflows[0].get("id")
    response = client.put(
        f"/workflows/{workflow_id}", headers={"x-api-key": "someapikey"}
    )
    # can't delete a provisioned workflow
    assert response.status_code == 403
    assert response.json() == {"detail": "Cannot update a provisioned workflow"}


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
def test_reprovision_workflow(monkeypatch, db_session, client, test_app):
    response = client.get("/workflows", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 3 workflows and 3 provisioned workflows
    workflows = response.json()
    provisioned_workflows = [w for w in workflows if w.get("provisioned")]
    assert len(provisioned_workflows) == 3

    # Step 2: Change environment variables (simulating new provisioning)
    monkeypatch.setenv("KEEP_WORKFLOWS_DIRECTORY", "./tests/provision/workflows_2")

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])

    # Reinitialize the TestClient with the new app instance
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(get_app())

    response = client.get("/workflows", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 2 workflows and 2 provisioned workflows
    workflows = response.json()
    provisioned_workflows = [w for w in workflows if w.get("provisioned")]
    assert len(provisioned_workflows) == 2


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"keepVictoriaMetrics1":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort": 1234}},"keepClickhouse1":{"type":"clickhouse","authentication":{"host":"http://localhost","port":1234,"username":"keep","password":"keep","database":"keep-db"}}}',
        },
    ],
    indirect=True,
)
def test_provision_provider(db_session, client, test_app):
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 3 workflows and 3 provisioned workflows
    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]
    assert len(provisioned_providers) == 2


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"keepVictoriaMetric2":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort": 1234}},"keepClickhouse1":{"type":"clickhouse","authentication":{"host":"http://localhost","port":1234,"username":"keep","password":"keep","database":"keep-db"}}}',
        },
    ],
    indirect=True,
)
def test_reprovision_provider(monkeypatch, db_session, client, test_app):
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]
    assert len(provisioned_providers) == 2

    # Step 2: Change environment variables (simulating new provisioning)
    monkeypatch.setenv(
        "KEEP_PROVIDERS",
        '{"keepPrometheus":{"type":"prometheus","authentication":{"url":"http://localhost","port":9090}}}',
    )

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])

    # Reinitialize the TestClient with the new app instance
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(app)

    # Step 3: Verify if the new provider is provisioned after reloading
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]
    assert len(provisioned_providers) == 1
    assert provisioned_providers[0]["type"] == "prometheus"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_DASHBOARDS": '[{"dashboard_name":"My Dashboard","dashboard_config":{"layout":[{"i":"w-1728223503577","x":0,"y":0,"w":3,"h":3,"minW":2,"minH":2,"static":false}],"widget_data":[{"i":"w-1728223503577","x":0,"y":0,"w":3,"h":3,"minW":2,"minH":2,"static":false,"thresholds":[{"value":0,"color":"#22c55e"},{"value":20,"color":"#ef4444"}],"preset":{"id":"11111111-1111-1111-1111-111111111111","name":"feed","options":[{"label":"CEL","value":"(!deleted && !dismissed)"},{"label":"SQL","value":{"sql":"(deleted=false AND dismissed=false)","params":{}}}],"created_by":null,"is_private":false,"is_noisy":false,"should_do_noise_now":false,"alerts_count":98,"static":true,"tags":[]},"name":"Test"}]}}]',
        },
    ],
    indirect=True,
)
def test_provision_dashboard(monkeypatch, db_session, client, test_app):
    response = client.get("/dashboard", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    dashboards = response.json()
    assert len(dashboards) == 1
    assert dashboards[0]["dashboard_name"] == "My Dashboard"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_DASHBOARDS": '{"dashboard_name": "a"}]',
        },
    ],
    indirect=True,
)
def test_provision_dashboard_invalid_json(monkeypatch, db_session, client, test_app):
    response = client.get("/dashboard", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    dashboards = response.json()
    assert len(dashboards) == 0


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_DASHBOARDS": '[{"dashboard_name":"Initial Dashboard","dashboard_config":{"layout":[{"i":"w-1728223503577","x":0,"y":0,"w":3,"h":3,"minW":2,"minH":2,"static":false}],"widget_data":[{"i":"w-1728223503577","x":0,"y":0,"w":3,"h":3,"minW":2,"minH":2,"static":false,"thresholds":[{"value":0,"color":"#22c55e"},{"value":20,"color":"#ef4444"}],"preset":{"id":"11111111-1111-1111-1111-111111111111","name":"feed","options":[{"label":"CEL","value":"(!deleted && !dismissed)"},{"label":"SQL","value":{"sql":"(deleted=false AND dismissed=false)","params":{}}}],"created_by":null,"is_private":false,"is_noisy":false,"should_do_noise_now":false,"alerts_count":98,"static":true,"tags":[]},"name":"Test"}]}}]',
        },
    ],
    indirect=True,
)
def test_reprovision_dashboard(monkeypatch, db_session, client, test_app):
    response = client.get("/dashboard", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    dashboards = response.json()
    assert len(dashboards) == 1
    assert dashboards[0]["dashboard_name"] == "Initial Dashboard"

    # Step 2: Change environment variables (simulating new provisioning)
    monkeypatch.setenv(
        "KEEP_DASHBOARDS",
        '[{"dashboard_name":"New Dashboard","dashboard_config":{"layout":[{"i":"w-1728223503578","x":0,"y":0,"w":3,"h":3,"minW":2,"minH":2,"static":false}],"widget_data":[{"i":"w-1728223503578","x":0,"y":0,"w":3,"h":3,"minW":2,"minH":2,"static":false,"thresholds":[{"value":0,"color":"#22c55e"},{"value":20,"color":"#ef4444"}],"preset":{"id":"11111111-1111-1111-1111-111111111112","name":"feed","options":[{"label":"CEL","value":"(!deleted && !dismissed)"},{"label":"SQL","value":{"sql":"(deleted=false AND dismissed=false)","params":{}}}],"created_by":null,"is_private":false,"is_noisy":false,"should_do_noise_now":false,"alerts_count":98,"static":true,"tags":[]},"name":"Test"}]}}]',
    )

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])

    # Reinitialize the TestClient with the new app instance
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(app)

    # Step 3: Verify if the new dashboard is provisioned after reloading
    response = client.get("/dashboard", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    dashboards = response.json()
    assert len(dashboards) == 2
    assert dashboards[1]["dashboard_name"] == "New Dashboard"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"keepVictoriaMetrics":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort": 1234}}}',
        },
    ],
    indirect=True,
)
def test_provision_provider_with_empty_tenant_table(db_session, client, test_app):
    """Test that provider provisioning fails when tenant table is empty with foreign key constraints enabled"""
    # Delete all entries from tenant table
    db_session.execute(text("DELETE FROM tenant"))
    db_session.commit()

    # Enable SQLite foreign keys
    db_session.execute(text("PRAGMA foreign_keys = ON;"))
    result = db_session.execute(text("PRAGMA foreign_keys;")).fetchone()
    assert result is not None and result[0] == 1, "Foreign keys not enabled"

    # Verify tenant table is empty
    tenant_count = db_session.execute(text("SELECT COUNT(*) FROM tenant")).fetchone()[0]
    assert tenant_count == 0, "Tenant table should be empty"

    # Import ProvidersService
    from keep.api.core.dependencies import SINGLE_TENANT_UUID
    from keep.providers.providers_service import ProvidersService

    # Call install_provider directly instead of provision_providers_from_env
    # This bypasses the exception handling in provision_providers_from_env
    with pytest.raises(Exception) as excinfo:
        ProvidersService.install_provider(
            tenant_id=SINGLE_TENANT_UUID,
            installed_by="system",
            provider_id="victoriametrics123",
            provider_name="keepVictoriaMetrics123",
            provider_type="victoriametrics",
            provider_config={"VMAlertHost": "http://localhost", "VMAlertPort": 1234},
            provisioned=True,
            validate_scopes=False,
        )

    # Verify that the error message is related to foreign key constraint violation
    error_msg = str(excinfo.value).lower()
    assert (
        "foreign key constraint" in error_msg
        or "FOREIGN KEY constraint failed" in str(excinfo.value)
        or "violates foreign key constraint" in error_msg
    )

    db_session.execute(text("PRAGMA foreign_keys = OFF;"))


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "NOAUTH"}],
    indirect=True,
)
def test_no_provisioned_providers_and_unset_env_vars(
    monkeypatch, db_session, client, test_app
):
    """Test behavior when there are no provisioned providers and env vars are unset"""
    # Import necessary modules
    from unittest.mock import patch

    from keep.providers.providers_service import ProvidersService

    # Mock get_all_provisioned_providers to return an empty list
    with (
        patch(
            "keep.providers.providers_service.get_all_provisioned_providers",
            return_value=[],
        ) as mock_get_providers,
        patch(
            "keep.providers.providers_service.ProvidersService.delete_provider"
        ) as mock_delete_provider,
    ):
        # Call provision_providers without setting any env vars
        ProvidersService.provision_providers("test-tenant")

        # Verify get_all_provisioned_providers was called
        mock_get_providers.assert_called_once_with("test-tenant")

        # Verify delete_provider was not called since there were no providers to delete
        mock_delete_provider.assert_not_called()


@pytest.mark.parametrize(
    "test_app",
    [{"AUTH_TYPE": "NOAUTH"}],
    indirect=True,
)
def test_delete_provisioned_providers_when_env_vars_unset(
    monkeypatch, db_session, client, test_app
):
    """Test deleting provisioned providers when env vars are unset"""
    # Import necessary modules
    from unittest.mock import MagicMock, patch

    from keep.providers.providers_service import ProvidersService

    # Create a mock provider
    mock_provider = MagicMock(id="test-id", name="test-provider", type="test-type")

    # Mock get_all_provisioned_providers to return our mock provider
    with (
        patch(
            "keep.providers.providers_service.get_all_provisioned_providers",
            return_value=[mock_provider],
        ) as mock_get_providers,
        patch(
            "keep.providers.providers_service.ProvidersService.delete_provider"
        ) as mock_delete_provider,
    ):
        # Call provision_providers without setting any env vars
        ProvidersService.provision_providers("test-tenant")

        # Verify get_all_provisioned_providers was called
        mock_get_providers.assert_called_once_with("test-tenant")

        # Verify delete_provider was called with correct parameters
        mock_delete_provider.assert_called_once_with(
            tenant_id="test-tenant",
            provider_id="test-id",
            allow_provisioned=True,
        )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"existingProvider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort": 1234}}}',
        },
    ],
    indirect=True,
)
def test_replace_existing_provisioned_provider(
    monkeypatch, db_session, client, test_app
):
    """Test that when a new provider is provisioned via KEEP_PROVIDERS without including
    the current provisioned provider, it removes the current one and installs the new one
    """

    # First verify the initial provider is installed
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]
    assert len(provisioned_providers) == 1
    # Provider name is in the details
    provider_details = provisioned_providers[0].get("details", {})
    assert provider_details.get("name") == "existingProvider"
    assert provisioned_providers[0]["type"] == "victoriametrics"

    # Change environment variable to new provider config that doesn't include the existing one
    monkeypatch.setenv(
        "KEEP_PROVIDERS",
        '{"newProvider":{"type":"prometheus","authentication":{"url":"http://localhost:9090"}}}',
    )

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # Manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(app)

    # Verify that the old provider is gone and new provider is installed
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]
    assert len(provisioned_providers) == 1
    provider_details = provisioned_providers[0].get("details", {})
    assert provider_details.get("name") == "newProvider"
    assert provisioned_providers[0]["type"] == "prometheus"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"rule1":{"description":"First rule","fingerprint_fields":["fingerprint","source"],"ignore_fields":["name"]}}}}',
        },
    ],
    indirect=True,
)
def test_delete_deduplication_rules_when_reprovisioning(
    monkeypatch, db_session, client, test_app
):
    """Test that deduplication rules are deleted when reprovisioning a provider without rules"""

    # First verify initial provider and rule are installed
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) - 1 == 1
    assert rules[1]["name"] == "rule1"

    # Update provider config without any deduplication rules
    monkeypatch.setenv(
        "KEEP_PROVIDERS",
        '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234}}}',
    )

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # Manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(app)

    # Verify the rule was deleted
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) == 0


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"rule1":{"description":"First rule","fingerprint_fields":["fingerprint","source"]},"rule2":{"description":"Second rule","fingerprint_fields":["alert_id"]}}}}',
        },
    ],
    indirect=True,
)
def test_provision_provider_with_multiple_deduplication_rules(
    db_session, client, test_app
):
    """Test provisioning a provider with multiple deduplication rules"""

    # Verify the provider and rules are installed
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) - 1 == 2

    rule1 = next(r for r in rules[1:] if r["name"] == "rule1")
    assert rule1["description"] == "First rule"
    assert rule1["fingerprint_fields"] == ["fingerprint", "source"]
    assert rule1["is_provisioned"] is True

    rule2 = next(r for r in rules if r["name"] == "rule2")
    assert rule2["description"] == "Second rule"
    assert rule2["fingerprint_fields"] == ["alert_id"]
    assert rule2["is_provisioned"] is True

    # Verify both rules are associated with the same provider
    assert rule1["provider_type"] == "victoriametrics"
    assert rule2["provider_type"] == "victoriametrics"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"rule1":{"description":"First rule","fingerprint_fields":["fingerprint","source"]},"rule2":{"description":"Second rule","fingerprint_fields":["alert_id"]}}}}',
        },
    ],
    indirect=True,
)
def test_update_deduplication_rules_when_reprovisioning(
    monkeypatch, db_session, client, test_app
):
    """Test that old deduplication rules are deleted and new ones are created when reprovisioning a provider with different rules"""

    # First verify initial provider and both rules are installed
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()
    assert len(rules) - 1 == 2  # Subtract 1 to exclude the default rule

    rule_names = [r["name"] for r in rules]
    assert "rule1" in rule_names
    assert "rule2" in rule_names

    # Update provider config with one rule removed and one rule updated and one new rule
    monkeypatch.setenv(
        "KEEP_PROVIDERS",
        '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"rule1":{"description":"Updated first rule","fingerprint_fields":["fingerprint","source","severity"]},"rule3":{"description":"New rule","fingerprint_fields":["alert_id","group"]}}}}',
    )

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # Manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(app)

    # Verify the rules were updated correctly
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()

    rule_names = [r["name"] for r in rules]
    assert "rule1" in rule_names
    assert "rule2" not in rule_names  # rule2 should be deleted
    assert "rule3" in rule_names  # rule3 should be added

    # Verify rule1 was updated
    rule1 = next(r for r in rules if r["name"] == "rule1")
    assert rule1["description"] == "Updated first rule"
    assert rule1["fingerprint_fields"] == ["fingerprint", "source", "severity"]

    # Verify rule3 was added
    rule3 = next(r for r in rules if r["name"] == "rule3")
    assert rule3["description"] == "New rule"
    assert rule3["fingerprint_fields"] == ["alert_id", "group"]

    # Verify both rules are associated with the same provider
    assert rule1["provider_type"] == "victoriametrics"
    assert rule3["provider_type"] == "victoriametrics"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"vm_rule1":{"description":"VM Rule","fingerprint_fields":["fingerprint"]}}}, "pagerduty_provider":{"type":"pagerduty","authentication":{"api_key":"somekey","routing_key":"routingkey123"},"deduplication_rules":{"pd_rule1":{"description":"PD Rule","fingerprint_fields":["id"]}}}}',
        },
    ],
    indirect=True,
)
def test_multiple_providers_with_deduplication_rules(
    monkeypatch, db_session, client, test_app
):
    """Test that deduplication rules for different providers don't interfere with each other"""

    # First verify both providers and their rules are installed
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()

    rule_names = [r["name"] for r in rules]
    assert "vm_rule1" in rule_names
    assert "pd_rule1" in rule_names

    # Update only the vm_provider, removing its rule and adding a new one
    monkeypatch.setenv(
        "KEEP_PROVIDERS",
        '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"vm_rule2":{"description":"New VM Rule","fingerprint_fields":["name"]}}}, "pagerduty_provider":{"type":"pagerduty","authentication":{"api_key":"somekey"},"deduplication_rules":{"pd_rule1":{"description":"PD Rule","fingerprint_fields":["id"]}}}}',
    )

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # Manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(app)

    # Verify the rules were updated correctly
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()

    rule_names = [r["name"] for r in rules]
    assert "vm_rule1" not in rule_names  # vm_rule1 should be deleted
    assert "vm_rule2" in rule_names  # vm_rule2 should be added
    assert "pd_rule1" in rule_names  # pd_rule1 should be kept

    # Verify vm_rule2 was added correctly
    vm_rule2 = next(r for r in rules if r["name"] == "vm_rule2")
    assert vm_rule2["description"] == "New VM Rule"
    assert vm_rule2["fingerprint_fields"] == ["name"]
    assert vm_rule2["provider_type"] == "victoriametrics"

    # Verify pd_rule1 was kept unchanged
    pd_rule1 = next(r for r in rules if r["name"] == "pd_rule1")
    assert pd_rule1["description"] == "PD Rule"
    assert pd_rule1["fingerprint_fields"] == ["id"]
    assert pd_rule1["provider_type"] == "pagerduty"


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "AUTH_TYPE": "NOAUTH",
            "KEEP_PROVIDERS": '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"vm_rule1":{"description":"VM Rule","fingerprint_fields":["fingerprint"]}}}, "pagerduty_provider":{"type":"pagerduty","authentication":{"api_key":"somekey","routing_key":"routingkey123"},"deduplication_rules":{"pd_rule1":{"description":"PD Rule","fingerprint_fields":["id"]}}}}',
        },
    ],
    indirect=True,
)
def test_deleting_provider_removes_deduplication_rules(
    monkeypatch, db_session, client, test_app
):
    """Test that when a provider is deleted, its associated deduplication rules are deleted as well"""

    # First verify both providers and their rules are installed
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()

    rule_names = [r["name"] for r in rules]
    assert "vm_rule1" in rule_names
    assert "pd_rule1" in rule_names

    # Remove the pagerduty_provider completely
    monkeypatch.setenv(
        "KEEP_PROVIDERS",
        '{"vm_provider":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort":1234},"deduplication_rules":{"vm_rule1":{"description":"VM Rule","fingerprint_fields":["fingerprint"]}}}}',
    )

    # Reload the app to apply the new environment changes
    importlib.reload(sys.modules["keep.api.api"])
    from keep.api.api import get_app

    app = get_app()

    # Manually trigger the startup event
    for event_handler in app.router.on_startup:
        asyncio.run(event_handler())

    # Manually trigger the provision resources
    from keep.api.config import provision_resources

    provision_resources()

    client = TestClient(app)

    # Verify the rules were updated correctly
    response = client.get("/deduplications", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    rules = response.json()

    rule_names = [r["name"] for r in rules]
    assert "vm_rule1" in rule_names  # vm_rule1 should still exist
    assert "pd_rule1" not in rule_names  # pd_rule1 should be deleted

    # Verify vm_rule1 is unchanged
    vm_rule1 = next(r for r in rules if r["name"] == "vm_rule1")
    assert vm_rule1["description"] == "VM Rule"
    assert vm_rule1["fingerprint_fields"] == ["fingerprint"]
    assert vm_rule1["provider_type"] == "victoriametrics"
