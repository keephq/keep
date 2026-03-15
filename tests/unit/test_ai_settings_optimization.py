import json
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session

from keep.api.core.db import (
    ExternalAIConfigAndMetadata,
    _adjust_settings_for_optimization_target,
    update_extrnal_ai_settings,
)
from keep.api.models.ai_external import ExternalAIConfigAndMetadataDto, ExternalAIDto
from keep.api.models.db.ai_external import ExternalAI


@pytest.fixture
def mock_session():
    return MagicMock(spec=Session)


@pytest.fixture
def sample_external_ai_config():
    return [
        {"name": "Model Accuracy Threshold", "value": 0.8, "type": "float"},
        {"name": "Correlation Threshold", "value": 0.8, "type": "float"},
        {"name": "Train Epochs", "value": 3, "type": "int"},
        {"name": "Create New Incidents", "value": True, "type": "bool"},
        {"name": "Enabled", "value": True, "type": "bool"},
    ]


@pytest.fixture
def mock_external_ai_config_metadata(sample_external_ai_config):
    mock_algo = MagicMock(spec=ExternalAI)
    mock_algo.unique_id = "test-algorithm"

    # Create a mock ExternalAIConfigAndMetadata instance
    mock_instance = MagicMock(spec=ExternalAIConfigAndMetadata)
    mock_instance.id = "test-id"
    mock_instance.algorithm_id = "test-algorithm"
    mock_instance.tenant_id = "test-tenant"
    mock_instance.settings = json.dumps(sample_external_ai_config)
    mock_instance.settings_proposed_by_algorithm = None
    mock_instance.feedback_logs = None
    mock_instance.optimization_target = "quality"  # Default

    return mock_instance


def test_adjust_settings_for_optimization_target_quality(sample_external_ai_config):
    adjusted_settings = _adjust_settings_for_optimization_target(
        sample_external_ai_config, "quality"
    )
    assert any(
        s["name"] == "Model Accuracy Threshold" and s["value"] == 0.95
        for s in adjusted_settings
    )
    assert any(
        s["name"] == "Correlation Threshold" and s["value"] == 0.95
        for s in adjusted_settings
    )
    assert any(s["name"] == "Train Epochs" and s["value"] == 5 for s in adjusted_settings)


def test_adjust_settings_for_optimization_target_speed(sample_external_ai_config):
    adjusted_settings = _adjust_settings_for_optimization_target(
        sample_external_ai_config, "speed"
    )
    assert any(
        s["name"] == "Model Accuracy Threshold" and s["value"] == 0.7
        for s in adjusted_settings
    )
    assert any(
        s["name"] == "Correlation Threshold" and s["value"] == 0.7
        for s in adjusted_settings
    )
    assert any(s["name"] == "Train Epochs" and s["value"] == 1 for s in adjusted_settings)


def test_adjust_settings_for_optimization_target_resource(sample_external_ai_config):
    adjusted_settings = _adjust_settings_for_optimization_target(
        sample_external_ai_config, "resource"
    )
    assert any(
        s["name"] == "Model Accuracy Threshold" and s["value"] == 0.6
        for s in adjusted_settings
    )
    assert any(
        s["name"] == "Correlation Threshold" and s["value"] == 0.6
        for s in adjusted_settings
    )
    assert any(s["name"] == "Train Epochs" and s["value"] == 1 for s in adjusted_settings)
    assert any(
        s["name"] == "Create New Incidents" and s["value"] is False
        for s in adjusted_settings
    )


def test_adjust_settings_for_optimization_target_unknown(sample_external_ai_config):
    original_settings = json.loads(json.dumps(sample_external_ai_config))  # Deep copy
    adjusted_settings = _adjust_settings_for_optimization_target(
        sample_external_ai_config, "unknown"
    )
    assert adjusted_settings == original_settings


@patch("keep.api.core.db.Session")
@patch("keep.api.core.db._adjust_settings_for_optimization_target")
@patch("keep.api.models.ai_external.ExternalAIConfigAndMetadataDto.from_orm")
def test_update_extrnal_ai_settings(
    mock_from_orm,
    mock_adjust_settings,
    mock_session_class,
    mock_session,
    mock_external_ai_config_metadata,
):
    # Arrange
    tenant_id = "test-tenant"
    ai_settings_dto = ExternalAIConfigAndMetadataDto(
        id="test-id",
        algorithm_id="test-algorithm",
        tenant_id=tenant_id,
        settings=[
            {"name": "Model Accuracy Threshold", "value": 0.5, "type": "float"},
        ],
        settings_proposed_by_algorithm=None,
        feedback_logs=None,
        algorithm=ExternalAIDto(name="Test", description="Test"),
        optimization_target="speed",
    )

    mock_session_class.return_value.__enter__.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = (
        mock_external_ai_config_metadata
    )
    mock_adjust_settings.return_value = [
        {"name": "Model Accuracy Threshold", "value": 0.7, "type": "float"}
    ]
    mock_from_orm.return_value = ai_settings_dto

    # Act
    result = update_extrnal_ai_settings(tenant_id, ai_settings_dto)

    # Assert
    mock_session.query.assert_called_once()
    mock_adjust_settings.assert_called_once_with(
        ai_settings_dto.settings, ai_settings_dto.optimization_target
    )
    assert mock_external_ai_config_metadata.settings == json.dumps(
        mock_adjust_settings.return_value
    )
    assert (
        mock_external_ai_config_metadata.optimization_target
        == ai_settings_dto.optimization_target
    )
    mock_session.add.assert_called_once_with(mock_external_ai_config_metadata)
    mock_session.commit.assert_called_once()
    mock_session.refresh.assert_called_once_with(mock_external_ai_config_metadata)
    mock_from_orm.assert_called_once_with(mock_external_ai_config_metadata)
    assert result == ai_settings_dto


@patch("keep.api.core.db.Session")
def test_update_extrnal_ai_settings_not_found(mock_session_class, mock_session):
    # Arrange
    tenant_id = "test-tenant"
    ai_settings_dto = ExternalAIConfigAndMetadataDto(
        id="non-existent-id",
        algorithm_id="test-algorithm",
        tenant_id=tenant_id,
        settings=[],
        settings_proposed_by_algorithm=None,
        feedback_logs=None,
        algorithm=ExternalAIDto(name="Test", description="Test"),
        optimization_target="quality",
    )

    mock_session_class.return_value.__enter__.return_value = mock_session
    mock_session.query.return_value.filter.return_value.first.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="External AI setting not found"):
        update_extrnal_ai_settings(tenant_id, ai_settings_dto)

