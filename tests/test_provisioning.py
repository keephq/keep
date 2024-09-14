import importlib
import sys

import pytest
from fastapi.testclient import TestClient

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
            "KEEP_PROVIDERS": '{"keepVictoriaMetrics":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort": 1234}},"keepClickhouse1":{"type":"clickhouse","authentication":{"host":"http://localhost","port":1234,"username":"keep","password":"keep","database":"keep-db"}}}',
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
            "KEEP_PROVIDERS": '{"keepVictoriaMetrics":{"type":"victoriametrics","authentication":{"VMAlertHost":"http://localhost","VMAlertPort": 1234}},"keepClickhouse1":{"type":"clickhouse","authentication":{"host":"http://localhost","port":1234,"username":"keep","password":"keep","database":"keep-db"}}}',
        },
    ],
    indirect=True,
)
def test_reprovision_provder(monkeypatch, db_session, client, test_app):
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    # 3 workflows and 3 provisioned workflows
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

    client = TestClient(get_app())

    # Step 3: Verify if the new provider is provisioned after reloading
    response = client.get("/providers", headers={"x-api-key": "someapikey"})
    assert response.status_code == 200
    providers = response.json()
    provisioned_providers = [
        p for p in providers.get("installed_providers") if p.get("provisioned")
    ]
    assert len(provisioned_providers) == 1
    assert provisioned_providers[0]["type"] == "prometheus"
