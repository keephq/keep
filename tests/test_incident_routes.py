import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from datetime import datetime, timezone

from keep.api.models.incident import (
    IncidentDto,
    IncidentDtoIn,
    IncidentStatus,
    IncidentSeverity,
    MergeIncidentsRequestDto,
    SplitIncidentRequestDto
)
from keep.api.models.db.incident import Incident
from keep.api.core.db import get_incident_by_id
from keep.api.core.dependencies import SINGLE_TENANT_UUID

@pytest.fixture
def sample_incident_data():
    return {
        "name": "Test Incident",
        "summary": "Test incident for API testing",
        "status": "open",
        "severity": "high",
        "assignee": "test@example.com"
    }

def test_create_incident_endpoint(client, sample_incident_data):
    response = client.post("/api/v1/incidents", json=sample_incident_data)
    assert response.status_code == 202
    data = response.json()
    assert data["name"] == sample_incident_data["name"]
    assert data["summary"] == sample_incident_data["summary"]
    assert data["status"] == sample_incident_data["status"]
    assert data["severity"] == sample_incident_data["severity"]
    assert data["assignee"] == sample_incident_data["assignee"]

def test_get_incidents_meta_endpoint(client):
    response = client.get("/api/v1/incidents/meta")
    assert response.status_code == 200
    data = response.json()
    assert "statuses" in data
    assert "severities" in data
    assert "assignees" in data
    assert "sources" in data

def test_get_all_incidents_endpoint(client, sample_incident_data):
    # Create a test incident first
    create_response = client.post("/api/v1/incidents", json=sample_incident_data)
    assert create_response.status_code == 202

    # Test getting all incidents
    response = client.get("/api/v1/incidents")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["count"] > 0
    assert len(data["items"]) > 0

def test_get_incident_by_id_endpoint(client, sample_incident_data):
    # Create a test incident first
    create_response = client.post("/api/v1/incidents", json=sample_incident_data)
    assert create_response.status_code == 202
    incident_id = create_response.json()["id"]

    # Test getting specific incident
    response = client.get(f"/api/v1/incidents/{incident_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == incident_id
    assert data["name"] == sample_incident_data["name"]

def test_update_incident_endpoint(client, sample_incident_data):
    # Create a test incident first
    create_response = client.post("/api/v1/incidents", json=sample_incident_data)
    assert create_response.status_code == 202
    incident_id = create_response.json()["id"]

    # Update the incident
    updated_data = sample_incident_data.copy()
    updated_data["name"] = "Updated Incident"
    updated_data["status"] = "resolved"

    response = client.put(f"/api/v1/incidents/{incident_id}", json=updated_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Incident"
    assert data["status"] == "resolved"

def test_delete_incident_endpoint(client, sample_incident_data):
    # Create a test incident first
    create_response = client.post("/api/v1/incidents", json=sample_incident_data)
    assert create_response.status_code == 202
    incident_id = create_response.json()["id"]

    # Delete the incident
    response = client.delete(f"/api/v1/incidents/{incident_id}")
    assert response.status_code == 202

    # Verify incident is deleted
    get_response = client.get(f"/api/v1/incidents/{incident_id}")
    assert get_response.status_code == 404

def test_merge_incidents_endpoint(client, sample_incident_data):
    # Create two test incidents
    incident1 = client.post("/api/v1/incidents", json=sample_incident_data).json()
    incident2 = client.post("/api/v1/incidents", json=sample_incident_data).json()

    merge_data = {
        "source_incident_ids": [incident2["id"]],
        "destination_incident_id": incident1["id"]
    }

    response = client.post("/api/v1/incidents/merge", json=merge_data)
    assert response.status_code == 200
    data = response.json()
    assert data["destination_incident_id"] == incident1["id"]
    assert incident2["id"] in data["merged_incident_ids"]

def test_split_incident_endpoint(client, sample_incident_data):
    # Create two test incidents
    source_incident = client.post("/api/v1/incidents", json=sample_incident_data).json()
    dest_incident = client.post("/api/v1/incidents", json=sample_incident_data).json()

    # Add test alerts to source incident
    test_fingerprints = ["test_fingerprint_1", "test_fingerprint_2"]
    split_data = {
        "destination_incident_id": dest_incident["id"],
        "alert_fingerprints": test_fingerprints
    }

    response = client.post(f"/api/v1/incidents/{source_incident['id']}/split", json=split_data)
    assert response.status_code == 200
    data = response.json()
    assert data["destination_incident_id"] == dest_incident["id"]
    assert all(fp in data["moved_alert_fingerprints"] for fp in test_fingerprints)

def test_get_incident_alerts_endpoint(client, sample_incident_data):
    # Create a test incident
    incident = client.post("/api/v1/incidents", json=sample_incident_data).json()

    response = client.get(f"/api/v1/incidents/{incident['id']}/alerts")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "count" in data

def test_get_incident_workflows_endpoint(client, sample_incident_data):
    # Create a test incident
    incident = client.post("/api/v1/incidents", json=sample_incident_data).json()

    response = client.get(f"/api/v1/incidents/{incident['id']}/workflows")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "count" in data

def test_get_incident_facets_endpoint(client):
    response = client.get("/api/v1/incidents/facets")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_get_incident_facet_fields_endpoint(client):
    response = client.get("/api/v1/incidents/facets/fields")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0