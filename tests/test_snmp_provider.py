import pytest
import json
from unittest.mock import patch, MagicMock

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.snmp_provider.snmp_provider import (
    SnmpProvider,
    SnmpProviderAuthConfig,
)
from keep.api.models.alert import AlertSeverity, AlertStatus


@pytest.fixture
def mock_context_manager():
    return MagicMock(spec=ContextManager)


@pytest.fixture
def snmp_provider_config():
    return {
        "authentication": {
            "host": "127.0.0.1",
            "port": 162,
            "community": "public",
            "oid": "1.3.6.1.4.1.99999.1.1",
        }
    }


def test_snmp_provider_init(mock_context_manager, snmp_provider_config):
    provider = SnmpProvider(
        mock_context_manager, "snmp_test", ProviderConfig(**snmp_provider_config)
    )
    assert provider.provider_id == "snmp_test"
    assert provider.authentication_config.host == "127.0.0.1"
    assert provider.authentication_config.port == 162


def test_snmp_provider_validate_config_success(
    mock_context_manager, snmp_provider_config
):
    provider = SnmpProvider(
        mock_context_manager, "snmp_test", ProviderConfig(**snmp_provider_config)
    )
    try:
        provider.validate_config()
    except Exception as e:
        pytest.fail(f"validate_config failed unexpectedly: {e}")


def test_snmp_provider_validate_config_failure_missing_host(mock_context_manager):
    invalid_config = {
        "authentication": {
            "port": 162,
            "community": "public",
            "oid": "1.3.6.1.4.1.99999.1.1",
        }
    }
    with pytest.raises(
        TypeError
    ):  # Pydantic dataclass will raise TypeError for missing required fields
        SnmpProvider(
            mock_context_manager, "snmp_test", ProviderConfig(**invalid_config)
        )


def test_snmp_provider_notify(mock_context_manager, snmp_provider_config, caplog):
    provider = SnmpProvider(
        mock_context_manager, "snmp_test", ProviderConfig(**snmp_provider_config)
    )
    message = "Test SNMP Trap"

    with patch(
        "keep.providers.snmp_provider.snmp_provider.sendNotification"
    ) as mock_send_notification:
        # Mock the return value of sendNotification
        mock_send_notification.return_value = (None, None, None, None)  # no error

        with caplog.at_level(provider.logger.info):
            result = provider._notify(message=message)
            assert "Sending SNMP trap" in caplog.text
            assert "SNMP trap sent successfully." in caplog.text
            assert result == "SNMP trap sent successfully"

        # Assert that sendNotification was called with the correct arguments
        mock_send_notification.assert_called_once()
        args, kwargs = mock_send_notification.call_args

        # Check CommunityData
        community_data = args[1]
        assert community_data.communityName.prettyPrint() == "public"

        # Check UdpTransportTarget
        transport_target = args[2]
        assert transport_target.transportAddress == ("127.0.0.1", 162)

        # Check NotificationType for OID and message
        notification_type = args[5]
        var_binds = notification_type._varBinds

        # Assert the enterprise OID
        assert var_binds[0][0].prettyPrint() == "1.3.6.1.6.3.1.1.4.1.0"
        assert (
            var_binds[0][1].prettyPrint() == "1.3.6.1.4.1.99999.1.1"
        )  # The OID from config

        # Assert the message OID and value
        assert var_binds[1][0].prettyPrint() == "1.3.6.1.2.1.1.0"  # sysDescr.0
        assert var_binds[1][1].prettyPrint() == message


# Tests for webhook receiving functionality (Issue #2112)


def test_provider_display_name():
    """Test that PROVIDER_DISPLAY_NAME is set correctly."""
    assert SnmpProvider.PROVIDER_DISPLAY_NAME == "SNMP"


def test_provider_has_webhook_description():
    """Test that provider has webhook_description for receiving traps."""
    assert hasattr(SnmpProvider, "webhook_description")
    assert SnmpProvider.webhook_description is not None
    assert "SNMP" in SnmpProvider.webhook_description


def test_provider_has_webhook_template():
    """Test that provider has webhook_template for receiving traps."""
    assert hasattr(SnmpProvider, "webhook_template")
    assert SnmpProvider.webhook_template is not None


def test_parse_event_raw_body_with_dict():
    """Test parse_event_raw_body with dict input."""
    raw_body = {
        "oid": "1.3.6.1.4.1.12345.1.2.3",
        "message": "CPU usage is high",
        "source": "server01",
        "severity": "critical",
    }
    result = SnmpProvider.parse_event_raw_body(raw_body)
    assert result == raw_body


def test_parse_event_raw_body_with_json_bytes():
    """Test parse_event_raw_body with JSON bytes input."""
    raw_body = b'{"oid": "1.3.6.1.4.1.12345.1.2.3", "message": "Test alert", "severity": "warning"}'
    result = SnmpProvider.parse_event_raw_body(raw_body)
    assert result["oid"] == "1.3.6.1.4.1.12345.1.2.3"
    assert result["message"] == "Test alert"
    assert result["severity"] == "warning"


def test_parse_event_raw_body_with_json_string():
    """Test parse_event_raw_body with JSON string input."""
    raw_body = '{"oid": "1.3.6.1.4.1.12345", "message": "Test", "source": "host1"}'
    result = SnmpProvider.parse_event_raw_body(raw_body)
    assert result["oid"] == "1.3.6.1.4.1.12345"
    assert result["message"] == "Test"
    assert result["source"] == "host1"


def test_format_alert_critical_severity():
    """Test _format_alert with critical severity."""
    event = {
        "oid": "1.3.6.1.4.1.12345.1.2.3",
        "message": "Critical alert",
        "source": "server01",
        "severity": "critical",
    }
    alert = SnmpProvider._format_alert(event)
    assert alert.name == "Critical alert"
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.status == AlertStatus.FIRING
    assert alert.source == ["server01"]
    assert alert.fingerprint == "1.3.6.1.4.1.12345.1.2.3"


def test_format_alert_warning_severity():
    """Test _format_alert with warning severity."""
    event = {
        "oid": "1.3.6.1.4.1.12345",
        "message": "Warning alert",
        "severity": "warning",
    }
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.WARNING


def test_format_alert_error_severity():
    """Test _format_alert with error severity."""
    event = {"message": "Error alert", "severity": "error"}
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.HIGH


def test_format_alert_high_severity():
    """Test _format_alert with high severity."""
    event = {"message": "High alert", "severity": "high"}
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.HIGH


def test_format_alert_medium_severity():
    """Test _format_alert with medium severity."""
    event = {"message": "Medium alert", "severity": "medium"}
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.MEDIUM


def test_format_alert_low_severity():
    """Test _format_alert with low severity."""
    event = {"message": "Low alert", "severity": "low"}
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.LOW


def test_format_alert_info_severity():
    """Test _format_alert with info severity."""
    event = {"message": "Info alert", "severity": "info"}
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.INFO


def test_format_alert_unknown_severity():
    """Test _format_alert with unknown severity defaults to INFO."""
    event = {"message": "Unknown alert", "severity": "unknown_severity"}
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.INFO


def test_format_alert_no_severity():
    """Test _format_alert with no severity defaults to INFO."""
    event = {"message": "No severity alert"}
    alert = SnmpProvider._format_alert(event)
    assert alert.severity == AlertSeverity.INFO


def test_format_alert_minimal_data():
    """Test _format_alert with minimal data (only message)."""
    event = {"message": "Minimal alert"}
    alert = SnmpProvider._format_alert(event)
    assert alert.name == "Minimal alert"
    assert alert.source == ["snmp"]
    assert alert.fingerprint == "Minimal alert"


def test_format_alert_uses_oid_as_name():
    """Test _format_alert uses oid as name when message is missing."""
    event = {"oid": "1.3.6.1.4.1.12345.1.2.3"}
    alert = SnmpProvider._format_alert(event)
    assert alert.name == "1.3.6.1.4.1.12345.1.2.3"


def test_format_alert_source_as_list():
    """Test _format_alert converts string source to list."""
    event = {"message": "Test", "source": "host1"}
    alert = SnmpProvider._format_alert(event)
    assert alert.source == ["host1"]


def test_format_alert_source_already_list():
    """Test _format_alert keeps list source as list."""
    event = {"message": "Test", "source": ["host1", "host2"]}
    alert = SnmpProvider._format_alert(event)
    assert alert.source == ["host1", "host2"]


def test_format_alert_description():
    """Test _format_alert sets description correctly."""
    event = {"message": "Test message", "description": "Test description"}
    alert = SnmpProvider._format_alert(event)
    assert alert.description == "Test description"


def test_format_alert_timestamp():
    """Test _format_alert sets lastReceived from timestamp."""
    event = {"message": "Test", "timestamp": "2024-01-15T10:30:00Z"}
    alert = SnmpProvider._format_alert(event)
    assert alert.lastReceived == "2024-01-15T10:30:00Z"


def test_format_alert_fingerprint_from_oid():
    """Test _format_alert uses oid for fingerprint."""
    event = {"oid": "1.3.6.1.4.1.12345", "message": "Test"}
    alert = SnmpProvider._format_alert(event)
    assert alert.fingerprint == "1.3.6.1.4.1.12345"


def test_format_alert_fingerprint_fallback_to_message():
    """Test _format_alert uses message for fingerprint when oid is missing."""
    event = {"message": "Test message"}
    alert = SnmpProvider._format_alert(event)
    assert alert.fingerprint == "Test message"


def test_format_alert_provider_category():
    """Test provider has correct category."""
    assert SnmpProvider.PROVIDER_CATEGORY == ["Monitoring"]


def test_format_alert_provider_tags():
    """Test provider has correct tags."""
    assert "alert" in SnmpProvider.PROVIDER_TAGS


def test_format_alert_with_additional_fields():
    """Test _format_alert passes through additional fields."""
    event = {"message": "Test", "custom_field": "custom_value", "another_field": 123}
    alert = SnmpProvider._format_alert(event)
    assert alert.custom_field == "custom_value"
    assert alert.another_field == 123


def test_auth_config_metadata():
    """Test that auth config has proper metadata."""
    # Test that the dataclass fields have metadata
    host_field = SnmpProviderAuthConfig.__dataclass_fields__["host"]
    assert host_field.metadata["required"] == True
    assert "description" in host_field.metadata

    port_field = SnmpProviderAuthConfig.__dataclass_fields__["port"]
    assert port_field.metadata["required"] == False
    assert port_field.default == 162

    community_field = SnmpProviderAuthConfig.__dataclass_fields__["community"]
    assert community_field.metadata["sensitive"] == True


def test_notify_with_error_indication(
    mock_context_manager, snmp_provider_config, caplog
):
    """Test _notify handles error indication from pysnmp."""
    provider = SnmpProvider(
        mock_context_manager, "snmp_test", ProviderConfig(**snmp_provider_config)
    )

    with patch(
        "keep.providers.snmp_provider.snmp_provider.sendNotification"
    ) as mock_send_notification:
        mock_send_notification.return_value = ("Error indication", None, None, None)

        with pytest.raises(Exception) as exc_info:
            provider._notify(message="Test")
        assert "Error sending SNMP trap" in str(exc_info.value)


def test_notify_with_error_status(mock_context_manager, snmp_provider_config, caplog):
    """Test _notify handles error status from pysnmp."""
    provider = SnmpProvider(
        mock_context_manager, "snmp_test", ProviderConfig(**snmp_provider_config)
    )

    with patch(
        "keep.providers.snmp_provider.snmp_provider.sendNotification"
    ) as mock_send_notification:
        mock_send_notification.return_value = (
            None,
            "Error Status",
            1,
            [("1.3.6.1.2.1.1.0", "value")],
        )

        with pytest.raises(Exception) as exc_info:
            provider._notify(message="Test")
        assert "Error sending SNMP trap" in str(exc_info.value)


def test_query_not_implemented(mock_context_manager, snmp_provider_config):
    """Test that _query raises NotImplementedError."""
    provider = SnmpProvider(
        mock_context_manager, "snmp_test", ProviderConfig(**snmp_provider_config)
    )

    with pytest.raises(NotImplementedError) as exc_info:
        provider._query()
    assert "does not support querying" in str(exc_info.value)


def test_dispose(mock_context_manager, snmp_provider_config):
    """Test that dispose does nothing."""
    provider = SnmpProvider(
        mock_context_manager, "snmp_test", ProviderConfig(**snmp_provider_config)
    )
    # Should not raise any exception
    provider.dispose()
