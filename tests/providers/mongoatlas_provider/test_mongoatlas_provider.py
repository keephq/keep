"""
Unit tests for the MongoDB Atlas provider.

These tests verify:
  - Configuration validation (public_key, private_key, group_id)
  - Alert formatting from Atlas API responses and webhook payloads
  - Severity and status mapping
  - HTTP Digest Auth usage
  - Both pull mode (_get_alerts) and push mode (_format_alert)
  - Webhook with single alert and alerts list
  - validate_scopes connectivity check
"""

import datetime
import pytest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.mongoatlas_provider.mongoatlas_provider import (
    MongoAtlasProvider,
    MongoAtlasProviderAuthConfig,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    public_key="test-public-key",
    private_key="test-private-key",
    group_id="5f5a4a5e3b9a1a0001f3a1b2",
) -> MongoAtlasProvider:
    """Build a MongoAtlasProvider instance with the given config."""
    config = ProviderConfig(
        authentication={
            "public_key": public_key,
            "private_key": private_key,
            "group_id": group_id,
        }
    )
    ctx = ContextManager(tenant_id="test-tenant", workflow_id="test-workflow")
    return MongoAtlasProvider(ctx, "mongoatlas-test", config)


def _host_down_alert() -> dict:
    return {
        "id": "5f5a4a5e3b9a1a0001f3a1a1",
        "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
        "eventTypeName": "HOST_DOWN",
        "status": "OPEN",
        "severity": "CRITICAL",
        "humanReadable": "We could not reach your MongoDB process at host1:27017.",
        "hostnameAndPort": "host1:27017",
        "clusterName": "MyCluster",
        "replicaSetName": "rs0",
        "created": "2024-01-15T10:00:00Z",
        "updated": "2024-01-15T10:00:00Z",
    }


def _no_primary_alert() -> dict:
    return {
        "id": "5f5a4a5e3b9a1a0001f3a1a2",
        "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
        "eventTypeName": "NO_PRIMARY",
        "status": "OPEN",
        "severity": "CRITICAL",
        "humanReadable": "Your replica set has no primary.",
        "clusterName": "MyCluster",
        "replicaSetName": "rs0",
        "created": "2024-01-15T11:00:00Z",
        "updated": "2024-01-15T11:00:00Z",
    }


def _disk_full_alert() -> dict:
    return {
        "id": "5f5a4a5e3b9a1a0001f3a1a4",
        "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
        "eventTypeName": "DISK_FULL",
        "status": "OPEN",
        "severity": "WARNING",
        "humanReadable": "Disk usage on host1:27017 is at 85% capacity.",
        "hostnameAndPort": "host1:27017",
        "clusterName": "MyCluster",
        "metricName": "DISK_PARTITION_SPACE_PERCENT_FREE",
        "currentValue": {"number": 15.0, "units": "RAW_SCALAR"},
        "created": "2024-01-15T13:00:00Z",
        "updated": "2024-01-15T13:00:00Z",
    }


def _closed_alert() -> dict:
    return {
        "id": "5f5a4a5e3b9a1a0001f3a1a9",
        "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
        "eventTypeName": "HOST_DOWN",
        "status": "CLOSED",
        "severity": "CRITICAL",
        "humanReadable": "Alert resolved.",
        "hostnameAndPort": "host1:27017",
        "clusterName": "MyCluster",
        "created": "2024-01-15T10:00:00Z",
        "updated": "2024-01-15T10:30:00Z",
    }


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestMongoAtlasProviderConfig:
    def test_minimal_config(self):
        provider = _make_provider()
        assert provider.authentication_config.public_key == "test-public-key"
        assert provider.authentication_config.private_key == "test-private-key"
        assert provider.authentication_config.group_id == "5f5a4a5e3b9a1a0001f3a1b2"

    def test_config_fields_stored_correctly(self):
        provider = _make_provider(
            public_key="pub123",
            private_key="priv456",
            group_id="group789",
        )
        cfg = provider.authentication_config
        assert cfg.public_key == "pub123"
        assert cfg.private_key == "priv456"
        assert cfg.group_id == "group789"

    def test_get_auth_returns_digest(self):
        from requests.auth import HTTPDigestAuth

        provider = _make_provider(public_key="mypub", private_key="myprivate")
        auth = provider._get_auth()
        assert isinstance(auth, HTTPDigestAuth)
        assert auth.username == "mypub"
        assert auth.password == "myprivate"


# ---------------------------------------------------------------------------
# _alert_to_dto (pull mode)
# ---------------------------------------------------------------------------


class TestAlertToDto:
    def test_host_down_severity_critical(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        assert dto.severity == AlertSeverity.CRITICAL
        assert dto.status == AlertStatus.FIRING
        assert dto.name == "Host Down"
        assert "host1:27017" in dto.description

    def test_disk_full_severity_warning(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_disk_full_alert())
        assert dto.severity == AlertSeverity.WARNING
        assert dto.status == AlertStatus.FIRING

    def test_closed_alert_status_resolved(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_closed_alert())
        assert dto.status == AlertStatus.RESOLVED
        # CLOSED maps to INFO for severity (status-based fallback)
        assert dto.severity == AlertSeverity.CRITICAL  # severity field is CRITICAL

    def test_alert_id_preserved(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        assert dto.id == "5f5a4a5e3b9a1a0001f3a1a1"

    def test_source_is_mongoatlas(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        assert "mongoatlas" in dto.source

    def test_service_is_cluster_name(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        assert dto.service == "MyCluster"

    def test_service_falls_back_to_hostname(self):
        provider = _make_provider()
        alert = _host_down_alert()
        del alert["clusterName"]
        dto = provider._alert_to_dto(alert)
        assert dto.service == "host1:27017"

    def test_labels_include_event_type(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        assert dto.labels["event_type"] == "HOST_DOWN"
        assert dto.labels["cluster_name"] == "MyCluster"
        assert dto.labels["hostname"] == "host1:27017"
        assert dto.labels["replica_set"] == "rs0"
        assert dto.labels["group_id"] == "5f5a4a5e3b9a1a0001f3a1b2"

    def test_description_from_humanreadable(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        assert dto.description == "We could not reach your MongoDB process at host1:27017."

    def test_description_from_metric_when_no_humanreadable(self):
        provider = _make_provider()
        alert = {
            "id": "abc123",
            "groupId": "group456",
            "eventTypeName": "DISK_FULL",
            "status": "OPEN",
            "metricName": "DISK_PARTITION_SPACE_PERCENT_FREE",
            "currentValue": {"number": 10.0, "units": "RAW_SCALAR"},
        }
        dto = provider._alert_to_dto(alert)
        assert "DISK_PARTITION_SPACE_PERCENT_FREE" in dto.description

    def test_timestamp_parsed_correctly(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        # updated is "2024-01-15T10:00:00Z" — should be ISO formatted
        assert "2024-01-15" in dto.lastReceived

    def test_fingerprint_set(self):
        provider = _make_provider()
        dto = provider._alert_to_dto(_host_down_alert())
        assert dto.fingerprint is not None
        assert len(dto.fingerprint) > 0


# ---------------------------------------------------------------------------
# _format_alert (webhook mode) - static method
# ---------------------------------------------------------------------------


class TestFormatAlert:
    def test_single_alert_dict(self):
        result = MongoAtlasProvider._format_alert(_host_down_alert())
        assert isinstance(result, AlertDto)
        assert result.severity == AlertSeverity.CRITICAL

    def test_alerts_list_in_payload(self):
        payload = {"alerts": [_host_down_alert(), _no_primary_alert()]}
        result = MongoAtlasProvider._format_alert(payload)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_single_alert_in_list(self):
        payload = {"alerts": [_disk_full_alert()]}
        result = MongoAtlasProvider._format_alert(payload)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0].severity == AlertSeverity.WARNING

    def test_host_down_webhook(self):
        dto = MongoAtlasProvider._format_single_atlas_alert(_host_down_alert())
        assert dto.name == "Host Down"
        assert dto.severity == AlertSeverity.CRITICAL
        assert dto.status == AlertStatus.FIRING

    def test_closed_alert_resolved_status(self):
        dto = MongoAtlasProvider._format_single_atlas_alert(_closed_alert())
        assert dto.status == AlertStatus.RESOLVED

    def test_no_primary_alert(self):
        dto = MongoAtlasProvider._format_single_atlas_alert(_no_primary_alert())
        assert dto.name == "No Primary"
        assert dto.severity == AlertSeverity.CRITICAL
        assert dto.labels["replica_set"] == "rs0"

    def test_tracking_status_maps_to_firing(self):
        alert = _host_down_alert()
        alert["status"] = "TRACKING"
        dto = MongoAtlasProvider._format_single_atlas_alert(alert)
        assert dto.status == AlertStatus.FIRING

    def test_severity_high(self):
        alert = _host_down_alert()
        alert["severity"] = "HIGH"
        dto = MongoAtlasProvider._format_single_atlas_alert(alert)
        assert dto.severity == AlertSeverity.HIGH

    def test_severity_medium_maps_to_warning(self):
        alert = _host_down_alert()
        alert["severity"] = "MEDIUM"
        dto = MongoAtlasProvider._format_single_atlas_alert(alert)
        assert dto.severity == AlertSeverity.WARNING

    def test_severity_low_maps_to_info(self):
        alert = _host_down_alert()
        alert["severity"] = "LOW"
        dto = MongoAtlasProvider._format_single_atlas_alert(alert)
        assert dto.severity == AlertSeverity.INFO

    def test_severity_info_maps_to_info(self):
        alert = _host_down_alert()
        alert["severity"] = "INFO"
        dto = MongoAtlasProvider._format_single_atlas_alert(alert)
        assert dto.severity == AlertSeverity.INFO

    def test_severity_informational_maps_to_info(self):
        alert = _host_down_alert()
        alert["severity"] = "INFORMATIONAL"
        dto = MongoAtlasProvider._format_single_atlas_alert(alert)
        assert dto.severity == AlertSeverity.INFO

    def test_unknown_severity_defaults_to_info(self):
        alert = _host_down_alert()
        alert["severity"] = "UNKNOWN_LEVEL"
        dto = MongoAtlasProvider._format_single_atlas_alert(alert)
        assert dto.severity == AlertSeverity.INFO

    def test_fingerprint_set_on_webhook(self):
        dto = MongoAtlasProvider._format_single_atlas_alert(_host_down_alert())
        assert dto.fingerprint is not None

    def test_source_is_mongoatlas(self):
        dto = MongoAtlasProvider._format_single_atlas_alert(_host_down_alert())
        assert "mongoatlas" in dto.source

    def test_empty_alerts_list(self):
        payload = {"alerts": []}
        result = MongoAtlasProvider._format_alert(payload)
        assert isinstance(result, list)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Severity map completeness
# ---------------------------------------------------------------------------


class TestSeverityMap:
    def test_all_critical_variants_present(self):
        assert MongoAtlasProvider.SEVERITIES_MAP["CRITICAL"] == AlertSeverity.CRITICAL

    def test_all_warning_variants_present(self):
        assert MongoAtlasProvider.SEVERITIES_MAP["WARNING"] == AlertSeverity.WARNING
        assert MongoAtlasProvider.SEVERITIES_MAP["MEDIUM"] == AlertSeverity.WARNING

    def test_status_based_fallbacks(self):
        assert MongoAtlasProvider.SEVERITIES_MAP["OPEN"] == AlertSeverity.HIGH
        assert MongoAtlasProvider.SEVERITIES_MAP["TRACKING"] == AlertSeverity.WARNING
        assert MongoAtlasProvider.SEVERITIES_MAP["CLOSED"] == AlertSeverity.INFO

    def test_status_map_complete(self):
        assert MongoAtlasProvider.STATUS_MAP["OPEN"] == AlertStatus.FIRING
        assert MongoAtlasProvider.STATUS_MAP["TRACKING"] == AlertStatus.FIRING
        assert MongoAtlasProvider.STATUS_MAP["CLOSED"] == AlertStatus.RESOLVED


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:
    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_valid_credentials_returns_true(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["alerts_read"] is True

    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_invalid_credentials_returns_error_string(self, mock_get):
        import requests

        mock_get.side_effect = requests.exceptions.HTTPError("401 Unauthorized")

        provider = _make_provider()
        result = provider.validate_scopes()
        assert result["alerts_read"] != True
        assert "401" in str(result["alerts_read"]) or "Unauthorized" in str(
            result["alerts_read"]
        )

    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_validate_scopes_uses_correct_url(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        provider = _make_provider(group_id="mygroup123")
        provider.validate_scopes()

        call_args = mock_get.call_args
        assert "mygroup123" in call_args[0][0]
        assert "atlas/v2" in call_args[0][0]

    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_validate_scopes_uses_digest_auth(self, mock_get):
        from requests.auth import HTTPDigestAuth

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        provider = _make_provider(public_key="pub", private_key="priv")
        provider.validate_scopes()

        call_kwargs = mock_get.call_args[1]
        assert isinstance(call_kwargs["auth"], HTTPDigestAuth)


# ---------------------------------------------------------------------------
# _get_alerts (pull mode integration)
# ---------------------------------------------------------------------------


class TestGetAlerts:
    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_get_alerts_returns_list(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "results": [_host_down_alert(), _disk_full_alert()]
        }
        mock_get.return_value = mock_response

        provider = _make_provider()
        alerts = provider._get_alerts()

        assert len(alerts) == 2
        assert all(isinstance(a, AlertDto) for a in alerts)

    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_get_alerts_empty_results(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        provider = _make_provider()
        alerts = provider._get_alerts()
        assert alerts == []

    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_get_alerts_uses_correct_url(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        provider = _make_provider(group_id="proj999")
        provider._get_alerts()

        call_args = mock_get.call_args
        url = call_args[0][0]
        assert "proj999" in url
        assert "alerts" in url

    @patch("keep.providers.mongoatlas_provider.mongoatlas_provider.requests.get")
    def test_get_alerts_uses_digest_auth(self, mock_get):
        from requests.auth import HTTPDigestAuth

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response

        provider = _make_provider()
        provider._get_alerts()

        call_kwargs = mock_get.call_args[1]
        assert isinstance(call_kwargs["auth"], HTTPDigestAuth)
