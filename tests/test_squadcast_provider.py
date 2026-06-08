import os
import pytest
from keep.providers.squadcast_provider import SquadcastProvider
from unittest.mock import patch

API_KEY = "dummy_api_key"
INCIDENT_ID = "dummy_incident_id"
SERVICE_ID = "dummy_service_id"

@pytest.fixture
def provider():
    return SquadcastProvider(api_key=API_KEY)

@patch("requests.post")
def test_create_incident(mock_post, provider):
    mock_post.return_value.status_code = 201
    mock_post.return_value.json.return_value = {"id": INCIDENT_ID, "status": "triggered"}
    incident_data = {
        "title": "Test Incident",
        "description": "Something went wrong",
        "service_id": SERVICE_ID
    }
    result = provider.create_incident(incident_data)
    assert result["id"] == INCIDENT_ID
    assert result["status"] == "triggered"
    mock_post.assert_called_once()

@patch("requests.patch")
def test_update_incident(mock_patch, provider):
    mock_patch.return_value.status_code = 200
    mock_patch.return_value.json.return_value = {"id": INCIDENT_ID, "status": "acknowledged"}
    update_data = {"status": "acknowledged"}
    result = provider.update_incident(INCIDENT_ID, update_data)
    assert result["status"] == "acknowledged"
    mock_patch.assert_called_once()

@patch("requests.post")
def test_resolve_incident(mock_post, provider):
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {"id": INCIDENT_ID, "status": "resolved"}
    result = provider.resolve_incident(INCIDENT_ID)
    assert result["status"] == "resolved"
    mock_post.assert_called_once()

@patch("requests.get")
def test_get_incident(mock_get, provider):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"id": INCIDENT_ID, "status": "triggered"}
    result = provider.get_incident(INCIDENT_ID)
    assert result["id"] == INCIDENT_ID
    mock_get.assert_called_once()

@patch("requests.get")
def test_list_services(mock_get, provider):
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"services": [{"id": SERVICE_ID, "name": "Test Service"}]}
    result = provider.list_services()
    assert "services" in result
    assert result["services"][0]["id"] == SERVICE_ID
    mock_get.assert_called_once()
