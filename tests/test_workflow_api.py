from unittest.mock import patch

from fastapi import HTTPException
import pytest
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from tests.fixtures.client import setup_api_key, client, test_app  # noqa

VALID_API_KEY = "test-api-key"


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@patch("keep.api.routes.workflows.WorkflowStore.get_workflow")
def test_run_route_workflow_with_invalid_definition(
    mock_get_workflow, client, db_session, test_app
):
    mock_get_workflow.side_effect = ValueError("No such provider type: msql ")
    # Setup API key
    setup_api_key(db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin")
    # Make request
    response = client.post(
        "/workflows/invalid-workflow-id/run",
        json={"param1": "value1", "param2": "value2"},
        headers={"x-api-key": VALID_API_KEY},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Invalid workflow configuration: No such provider type: msql "
    }


@pytest.mark.parametrize("test_app", ["NO_AUTH"], indirect=True)
@patch("keep.api.routes.workflows.WorkflowStore.get_workflow")
def test_run_route_not_existing_workflow(
    mock_get_workflow, client, db_session, test_app
):
    mock_get_workflow.side_effect = HTTPException(
        status_code=404, detail="Workflow not-existing-workflow-id not found"
    )
    # Setup API key
    setup_api_key(db_session, VALID_API_KEY, tenant_id=SINGLE_TENANT_UUID, role="admin")
    # Make request
    response = client.post(
        "/workflows/not-existing-workflow-id/run",
        json={"param1": "value1", "param2": "value2"},
        headers={"x-api-key": VALID_API_KEY},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Workflow not-existing-workflow-id not found"}
