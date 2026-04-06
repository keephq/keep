"""
Tests for the QualiTorque provider.

Covers:
- _format_alert with various webhook payload shapes
- Severity and status mapping
- Edge cases (missing fields, empty payloads)
- validate_scopes behaviour
- _get_alerts pull mode
"""

from unittest.mock import MagicMock, patch

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.qualitorque_provider.qualitorque_provider import (
    QualitorqueProvider,
)


class TestFormatAlert:
    """Test _format_alert static method with webhook payloads."""

    def test_basic_environment_error(self):
        """Error event with all standard fields."""
        event = {
            "event_type": "EnvironmentError",
            "environment_name": "prod-checkout-v2",
            "environment_id": "env-abc123",
            "computed_status": "error",
            "message": "Terraform apply failed: resource quota exceeded",
            "owner": {"email": "alice@example.com"},
            "blueprint": "checkout-service",
            "space": "production",
            "timestamp": "2026-04-06T12:00:00Z",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.id == "env-abc123"
        assert alert.name == "prod-checkout-v2"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert "quota exceeded" in alert.description
        assert alert.environment == "prod-checkout-v2"
        assert alert.owner == "alice@example.com"
        assert alert.blueprint == "checkout-service"
        assert alert.space == "production"
        assert alert.source == ["qualitorque"]

    def test_environment_active(self):
        """Active environment maps to RESOLVED."""
        event = {
            "event_type": "EnvironmentActive",
            "environment_name": "staging-api",
            "environment_id": "env-xyz",
            "computed_status": "active",
            "message": "Environment is ready",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_drift_detected(self):
        """Drift detection maps to WARNING/FIRING."""
        event = {
            "event_type": "DriftDetected",
            "environment_name": "prod-db",
            "environment_id": "env-drift1",
            "computed_status": "drift_detected",
            "message": "Configuration drift detected in RDS instance",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

    def test_environment_ended(self):
        """Ended environment maps to RESOLVED/INFO."""
        event = {
            "event_type": "EnvironmentEnded",
            "environment_name": "temp-test",
            "environment_id": "env-end1",
            "computed_status": "ended",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED
        assert alert.severity == AlertSeverity.INFO

    def test_environment_launching(self):
        """Launching environment maps to ACKNOWLEDGED/INFO."""
        event = {
            "event_type": "EnvironmentLaunching",
            "environment_name": "dev-feature-x",
            "environment_id": "env-launch1",
            "computed_status": "launching",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.severity == AlertSeverity.INFO

    def test_force_ended(self):
        """Force-ended environment maps to HIGH severity."""
        event = {
            "event_type": "EnvironmentForceEnded",
            "environment_name": "stuck-env",
            "environment_id": "env-force1",
            "computed_status": "force_ended",
            "message": "Environment was force-terminated due to timeout",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.FIRING

    def test_active_with_error(self):
        """Active-with-error maps to WARNING/FIRING."""
        event = {
            "event_type": "EnvironmentActiveWithError",
            "environment_name": "partial-env",
            "environment_id": "env-awe1",
            "computed_status": "active_with_error",
            "message": "Environment active but some resources failed",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING


class TestFormatAlertAlternativeKeys:
    """Test _format_alert with alternative key names (sandbox_ prefix, etc.)."""

    def test_sandbox_style_keys(self):
        """Older Torque payloads may use sandbox_ prefix."""
        event = {
            "notification_type": "SandboxError",
            "sandbox_name": "my-sandbox",
            "sandbox_id": "sb-123",
            "status": "error",
            "details": "Deployment timed out",
            "initiated_by": "bob@example.com",
            "blueprint_name": "web-app",
            "space_name": "dev",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.id == "sb-123"
        assert alert.name == "my-sandbox"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING
        assert "timed out" in alert.description
        assert alert.owner == "bob@example.com"
        assert alert.blueprint == "web-app"
        assert alert.space == "dev"

    def test_type_key(self):
        """Payload with 'type' instead of 'event_type'."""
        event = {
            "type": "EnvironmentDeploying",
            "name": "deploy-test",
            "id": "env-dep1",
            "status": "deploying",
        }
        alert = QualitorqueProvider._format_alert(event)

        assert alert.id == "env-dep1"
        assert alert.name == "deploy-test"
        assert alert.event_type == "EnvironmentDeploying"
        assert alert.status == AlertStatus.ACKNOWLEDGED


class TestFormatAlertEdgeCases:
    """Test _format_alert edge cases."""

    def test_empty_payload(self):
        """Empty dict should not crash."""
        alert = QualitorqueProvider._format_alert({})

        assert alert.id == ""
        assert alert.name == "unknown"
        assert alert.source == ["qualitorque"]
        assert alert.description == "QualiTorque event: unknown"

    def test_missing_status_infers_from_event_type(self):
        """When status is missing, infer from event_type keywords."""
        # Error event type
        alert = QualitorqueProvider._format_alert(
            {"event_type": "EnvironmentError", "environment_name": "test"}
        )
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.status == AlertStatus.FIRING

        # Drift event type
        alert = QualitorqueProvider._format_alert(
            {"event_type": "DriftDetected"}
        )
        assert alert.severity == AlertSeverity.WARNING
        assert alert.status == AlertStatus.FIRING

        # Launch event type
        alert = QualitorqueProvider._format_alert(
            {"event_type": "EnvironmentLaunched"}
        )
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.ACKNOWLEDGED

        # End event type
        alert = QualitorqueProvider._format_alert(
            {"event_type": "EnvironmentEnded"}
        )
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

        # Active event type
        alert = QualitorqueProvider._format_alert(
            {"event_type": "EnvironmentActive"}
        )
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.RESOLVED

    def test_owner_as_string(self):
        """Owner can be a plain string instead of a dict."""
        event = {
            "event_type": "EnvironmentError",
            "environment_name": "test",
            "environment_id": "env-1",
            "computed_status": "error",
            "owner": "alice@example.com",
        }
        alert = QualitorqueProvider._format_alert(event)
        assert alert.owner == "alice@example.com"

    def test_error_message_field(self):
        """Description from error_message field."""
        event = {
            "event_type": "EnvironmentFailed",
            "environment_name": "broken",
            "environment_id": "env-2",
            "computed_status": "failed",
            "error_message": "Module not found: eks-cluster",
        }
        alert = QualitorqueProvider._format_alert(event)
        assert "Module not found" in alert.description

    def test_created_at_timestamp(self):
        """Fallback to created_at for lastReceived."""
        event = {
            "event_type": "EnvironmentError",
            "environment_name": "ts-test",
            "environment_id": "env-ts",
            "status": "error",
            "created_at": "2026-04-06T08:30:00Z",
        }
        alert = QualitorqueProvider._format_alert(event)
        assert alert.lastReceived == "2026-04-06T08:30:00Z"


class TestValidateScopes:
    """Test validate_scopes API connectivity check."""

    @patch("keep.providers.qualitorque_provider.qualitorque_provider.requests")
    def test_successful_auth(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        provider = _create_provider(
            torque_host="https://portal.qtorque.io",
            torque_space="my-space",
            torque_token="tok-secret",
        )
        result = provider.validate_scopes()

        assert result["authenticated"] is True
        mock_requests.get.assert_called_once()
        call_args = mock_requests.get.call_args
        assert "my-space" in call_args[0][0]

    @patch("keep.providers.qualitorque_provider.qualitorque_provider.requests")
    def test_auth_failure_401(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests.get.return_value = mock_response

        provider = _create_provider(
            torque_host="https://portal.qtorque.io",
            torque_space="my-space",
            torque_token="bad-token",
        )
        result = provider.validate_scopes()

        assert result["authenticated"] != True
        assert "401" in str(result["authenticated"])

    @patch("keep.providers.qualitorque_provider.qualitorque_provider.requests")
    def test_auth_failure_403(self, mock_requests):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_requests.get.return_value = mock_response

        provider = _create_provider(
            torque_host="https://portal.qtorque.io",
            torque_space="my-space",
            torque_token="bad-token",
        )
        result = provider.validate_scopes()

        assert result["authenticated"] != True
        assert "403" in str(result["authenticated"])

    @patch("keep.providers.qualitorque_provider.qualitorque_provider.requests")
    def test_connection_error(self, mock_requests):
        import requests as real_requests

        mock_requests.get.side_effect = real_requests.exceptions.ConnectionError(
            "DNS resolution failed"
        )
        mock_requests.exceptions = real_requests.exceptions

        provider = _create_provider(
            torque_host="https://unreachable.example.com",
            torque_space="my-space",
            torque_token="tok",
        )
        result = provider.validate_scopes()

        assert result["authenticated"] != True
        assert "connect" in str(result["authenticated"]).lower()


class TestGetAlerts:
    """Test _get_alerts pull mode."""

    @patch("keep.providers.qualitorque_provider.qualitorque_provider.requests")
    def test_returns_error_environments_only(self, mock_requests):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = [
            {
                "id": "env-1",
                "name": "healthy-env",
                "definition_name": "web-app",
                "computed_status": "Active",
                "owner": {"email": "a@b.com"},
            },
            {
                "id": "env-2",
                "name": "broken-env",
                "definition_name": "api-service",
                "computed_status": "Error",
                "owner": {"email": "c@d.com"},
                "last_used": "2026-04-06T10:00:00Z",
            },
            {
                "id": "env-3",
                "name": "drifted-env",
                "definition_name": "db-cluster",
                "computed_status": "drift_detected",
                "owner": {"email": "e@f.com"},
            },
        ]
        mock_requests.get.return_value = mock_response

        provider = _create_provider(
            torque_host="https://portal.qtorque.io",
            torque_space="prod",
            torque_token="tok",
        )
        alerts = provider._get_alerts()

        # Only error and drift_detected should be returned, not active
        assert len(alerts) == 2
        assert alerts[0].id == "env-2"
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert alerts[1].id == "env-3"
        assert alerts[1].severity == AlertSeverity.WARNING

    @patch("keep.providers.qualitorque_provider.qualitorque_provider.requests")
    def test_api_failure_raises(self, mock_requests):
        mock_response = MagicMock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_requests.get.return_value = mock_response

        provider = _create_provider(
            torque_host="https://portal.qtorque.io",
            torque_space="prod",
            torque_token="tok",
        )

        with pytest.raises(Exception, match="Failed to fetch"):
            provider._get_alerts()

    @patch("keep.providers.qualitorque_provider.qualitorque_provider.requests")
    def test_empty_environment_list(self, mock_requests):
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.json.return_value = []
        mock_requests.get.return_value = mock_response

        provider = _create_provider(
            torque_host="https://portal.qtorque.io",
            torque_space="prod",
            torque_token="tok",
        )
        alerts = provider._get_alerts()

        assert alerts == []


class TestSeverityMapping:
    """Test all severity map entries."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            ("error", AlertSeverity.CRITICAL),
            ("failed", AlertSeverity.CRITICAL),
            ("force_ended", AlertSeverity.HIGH),
            ("ending_failed", AlertSeverity.HIGH),
            ("drift_detected", AlertSeverity.WARNING),
            ("active_with_error", AlertSeverity.WARNING),
            ("launching", AlertSeverity.INFO),
            ("deploying", AlertSeverity.INFO),
            ("ending", AlertSeverity.INFO),
            ("terminating", AlertSeverity.INFO),
            ("active", AlertSeverity.INFO),
            ("ended", AlertSeverity.INFO),
        ],
    )
    def test_severity_map(self, status, expected):
        assert QualitorqueProvider.SEVERITIES_MAP[status] == expected


class TestStatusMapping:
    """Test all status map entries."""

    @pytest.mark.parametrize(
        "status,expected",
        [
            ("error", AlertStatus.FIRING),
            ("failed", AlertStatus.FIRING),
            ("ending_failed", AlertStatus.FIRING),
            ("force_ended", AlertStatus.FIRING),
            ("drift_detected", AlertStatus.FIRING),
            ("active_with_error", AlertStatus.FIRING),
            ("launching", AlertStatus.ACKNOWLEDGED),
            ("deploying", AlertStatus.ACKNOWLEDGED),
            ("ending", AlertStatus.ACKNOWLEDGED),
            ("terminating", AlertStatus.ACKNOWLEDGED),
            ("active", AlertStatus.RESOLVED),
            ("ended", AlertStatus.RESOLVED),
        ],
    )
    def test_status_map(self, status, expected):
        assert QualitorqueProvider.STATUS_MAP[status] == expected


# --- Helpers ---


def _create_provider(
    torque_host="https://portal.qtorque.io",
    torque_space="default",
    torque_token="test-token",
) -> QualitorqueProvider:
    """Create a QualitorqueProvider instance for testing."""
    context_manager = MagicMock()
    config = MagicMock()
    config.authentication = {
        "torque_host": torque_host,
        "torque_space": torque_space,
        "torque_token": torque_token,
    }
    provider = QualitorqueProvider(
        context_manager=context_manager,
        provider_id="qualitorque-test",
        config=config,
    )
    return provider
