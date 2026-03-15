import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from keep.api.api import get_app
from keep.api.core.db import ExternalAIConfigAndMetadata
from keep.api.models.ai_external import ExternalAIConfigAndMetadataDto, ExternalAIDto
from keep.api.models.db.ai_external import ExternalAI, external_ai_transformers


@patch("keep.api.core.db.get_or_create_external_ai_settings")
@patch("keep.api.core.db.get_alerts_count")
@patch("keep.api.core.db.get_first_alert_datetime")
@patch("keep.api.core.db.get_incidents_count")
def test_get_ai_stats(
    mock_get_incidents_count,
    mock_get_first_alert_datetime,
    mock_get_alerts_count,
    mock_get_or_create_external_ai_settings,
):
    client = TestClient(get_app())
    # Arrange
    tenant_id = "test_tenant"
    mock_authenticated_entity = MagicMock()
    mock_authenticated_entity.tenant_id = tenant_id

    # Mock the return value of get_or_create_external_ai_settings
    sample_settings = [
        {"name": "Model Accuracy Threshold", "value": 0.9, "type": "float"},
        {"name": "Correlation Threshold", "value": 0.9, "type": "float"},
        {"name": "Train Epochs", "value": 3, "type": "int"},
        {"name": "Create New Incidents", "value": True, "type": "bool"},
        {"name": "Enabled", "value": True, "type": "bool"},
    ]
    mock_ai_config_db = ExternalAIConfigAndMetadata(
        id="algo-id",
        algorithm_id=external_ai_transformers.unique_id,
        tenant_id=tenant_id,
        settings=json.dumps(sample_settings),
        settings_proposed_by_algorithm=None,
        feedback_logs=None,
        optimization_target="quality",
    )
    mock_ai_config_dto = ExternalAIConfigAndMetadataDto.from_orm(mock_ai_config_db)
    mock_get_or_create_external_ai_settings.return_value = [mock_ai_config_dto]

    mock_get_alerts_count.return_value = 100
    mock_get_first_alert_datetime.return_value = datetime.now()
    mock_get_incidents_count.return_value = 50

    # Act
    with patch(
        "keep.api.routes.ai.IdentityManagerFactory.get_auth_verifier",
        return_value=lambda: mock_authenticated_entity,
    ):
        response = client.get("/ai/stats")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["alerts_count"] == 100
    assert len(data["algorithm_configs"]) == 1
    assert data["algorithm_configs"][0]["id"] == "algo-id"
    assert data["algorithm_configs"][0]["optimization_target"] == "quality"


@patch("keep.api.core.db.get_or_create_external_ai_settings")
@patch("keep.api.core.db.update_extrnal_ai_settings")
def test_update_ai_settings_endpoint(
    mock_update_extrnal_ai_settings,
    mock_get_or_create_external_ai_settings,
):
    client = TestClient(get_app())
    # Arrange
    tenant_id = "test_tenant"
    algorithm_id = "test-algorithm_1"
    mock_authenticated_entity = MagicMock()
    mock_authenticated_entity.tenant_id = tenant_id

    # Original settings for the mock DB object
    original_settings_list = [
        {"name": "Model Accuracy Threshold", "value": 0.8, "type": "float"},
        {"name": "Correlation Threshold", "value": 0.8, "type": "float"},
        {"name": "Train Epochs", "value": 3, "type": "int"},
        {"name": "Create New Incidents", "value": True, "type": "bool"},
        {"name": "Enabled", "value": True, "type": "bool"},
    ]

    # DTO that the client sends
    updated_dto = ExternalAIConfigAndMetadataDto(
        id="algo-id",
        algorithm_id=algorithm_id,
        tenant_id=tenant_id,
        settings=original_settings_list,
        settings_proposed_by_algorithm=None,
        feedback_logs=None,
        algorithm=ExternalAIDto(name="Test", description="Test"),
        optimization_target="speed",  # New optimization target
    )

    # Mock the return value of update_extrnal_ai_settings
    # It should return a DTO with adjusted settings based on "speed"
    adjusted_settings_list = [
        {"name": "Model Accuracy Threshold", "value": 0.7, "type": "float"},
        {"name": "Correlation Threshold", "value": 0.7, "type": "float"},
        {"name": "Train Epochs", "value": 1, "type": "int"},
        {"name": "Create New Incidents", "value": True, "type": "bool"},
        {"name": "Enabled", "value": True, "type": "bool"},
    ]
    mock_update_extrnal_ai_settings.return_value = ExternalAIConfigAndMetadataDto(
        id="algo-id",
        algorithm_id=algorithm_id,
        tenant_id=tenant_id,
        settings=adjusted_settings_list,  # Adjusted settings
        settings_proposed_by_algorithm=None,
        feedback_logs=None,
        algorithm=ExternalAIDto(name="Test", description="Test"),
        optimization_target="speed",
    )

    # Act
    with patch(
        "keep.api.routes.ai.IdentityManagerFactory.get_auth_verifier",
        return_value=lambda: mock_authenticated_entity,
    ):
        response = client.put(f"/ai/{algorithm_id}/settings", json=updated_dto.dict())

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "algo-id"
    assert data["optimization_target"] == "speed"
    # Verify that the settings are indeed adjusted
    assert any(
        s["name"] == "Model Accuracy Threshold" and s["value"] == 0.7
        for s in data["settings"]
    )
    assert any(s["name"] == "Train Epochs" and s["value"] == 1 for s in data["settings"])

    # Verify that update_extrnal_ai_settings was called with the correct DTO
    mock_update_extrnal_ai_settings.assert_called_once()
    called_dto = mock_update_extrnal_ai_settings.call_args[0][1]
    assert called_dto.optimization_target == "speed"
    assert called_dto.id == updated_dto.id
    assert called_dto.algorithm_id == updated_dto.algorithm_id
    assert called_dto.tenant_id == updated_dto.tenant_id
    assert called_dto.settings == updated_dto.settings  # Should be the original settings from the DTO, then adjusted in db layer

