"""
Tests for the SolarWinds provider.

Covers webhook formatting (_format_alert), severity mapping, status
determination, alerts_mock compatibility, and provider metadata.
"""

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.solarwinds_provider.solarwinds_provider import SolarwindsProvider

# --- Webhook (_format_alert) tests ---


class TestSolarwindsFormatAlert:
    """Tests for _format_alert (webhook path)."""

    def test_critical_node_down(self):
        event = {
            "alert_name": "Node is Down",
            "alert_message": "Node sw-core-01 is unreachable",
            "severity": "0",
            "alert_active_id": "12345",
            "alert_object_id": "67890",
            "alert_id": "789",
            "object_name": "sw-core-01",
            "object_type": "Orion.Nodes",
            "node_name": "sw-core-01",
            "ip_address": "10.0.1.1",
            "triggered_datetime": "2026-02-24T10:30:00.0000000Z",
            "acknowledged": "false",
            "notification_type": "PROBLEM",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING.value
        assert alert.severity == AlertSeverity.CRITICAL.value
        assert alert.name == "Node is Down"
        assert alert.description == "Node sw-core-01 is unreachable"
        assert alert.node_name == "sw-core-01"
        assert alert.source == ["solarwinds"]
        assert alert.id == "12345"

    def test_warning_alert(self):
        event = {
            "alert_name": "High CPU",
            "severity": "2",
            "notification_type": "PROBLEM",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING.value
        assert alert.status == AlertStatus.FIRING.value

    def test_serious_alert(self):
        event = {
            "alert_name": "Interface Down",
            "severity": "1",
            "notification_type": "PROBLEM",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.HIGH.value

    def test_informational_alert(self):
        event = {
            "alert_name": "Config Change",
            "severity": "3",
            "notification_type": "PROBLEM",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO.value

    def test_notice_alert(self):
        event = {
            "alert_name": "Scheduled Event",
            "severity": "4",
            "notification_type": "PROBLEM",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.LOW.value

    def test_severity_integer(self):
        event = {
            "alert_name": "Test",
            "severity": 0,
            "notification_type": "PROBLEM",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL.value

    def test_severity_named_string(self):
        event = {
            "alert_name": "Test",
            "severity": "Critical",
            "notification_type": "PROBLEM",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL.value

    def test_severity_named_warning(self):
        event = {"alert_name": "Test", "severity": "Warning", "acknowledged": "false"}
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING.value

    def test_severity_named_informational(self):
        event = {
            "alert_name": "Test",
            "severity": "Informational",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO.value

    def test_unknown_severity_defaults_to_info(self):
        event = {"alert_name": "Test", "severity": "garbage", "acknowledged": "false"}
        alert = SolarwindsProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO.value

    def test_recovery(self):
        event = {
            "alert_name": "Node is Down",
            "severity": "0",
            "notification_type": "RECOVERY",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.RESOLVED.value

    def test_acknowledged_string_true(self):
        event = {
            "alert_name": "Node Down",
            "severity": "0",
            "notification_type": "PROBLEM",
            "acknowledged": "true",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.ACKNOWLEDGED.value
        assert alert.acknowledged is True

    def test_acknowledged_string_yes(self):
        event = {
            "alert_name": "Test",
            "severity": "0",
            "acknowledged": "yes",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.ACKNOWLEDGED.value

    def test_acknowledged_bool_true(self):
        event = {
            "alert_name": "Test",
            "severity": "0",
            "acknowledged": True,
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.ACKNOWLEDGED.value

    def test_acknowledged_string_1(self):
        event = {
            "alert_name": "Test",
            "severity": "0",
            "acknowledged": "1",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.ACKNOWLEDGED.value

    def test_not_acknowledged(self):
        event = {
            "alert_name": "Test",
            "severity": "0",
            "acknowledged": "false",
            "notification_type": "PROBLEM",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.status == AlertStatus.FIRING.value
        assert alert.acknowledged is False

    def test_acknowledgement_notification_type(self):
        event = {
            "alert_name": "Test",
            "severity": "0",
            "notification_type": "ACKNOWLEDGEMENT",
            "acknowledged": "false",
        }
        # notification_type ACKNOWLEDGEMENT but acknowledged=false
        # acknowledged flag takes priority
        alert = SolarwindsProvider._format_alert(event)
        # Since acknowledged is false, falls through to notification_type map
        assert alert.status == AlertStatus.ACKNOWLEDGED.value

    def test_id_from_alert_active_id(self):
        event = {
            "alert_name": "Test",
            "alert_active_id": "12345",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.id == "12345"

    def test_id_fallback_to_alert_id_and_object(self):
        event = {
            "alert_name": "Test",
            "alert_id": "789",
            "object_name": "node-01",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.id == "789_node-01"

    def test_timestamp_passthrough(self):
        event = {
            "alert_name": "Test",
            "triggered_datetime": "2026-02-24T10:30:00Z",
            "acknowledged": "false",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert "2026-02-24T10:30:00" in alert.lastReceived

    def test_empty_event(self):
        """Empty webhook payload should not crash."""
        alert = SolarwindsProvider._format_alert({})
        assert alert is not None
        assert alert.source == ["solarwinds"]
        assert alert.name == "SolarWinds Alert"

    def test_all_fields_populated(self):
        event = {
            "alert_name": "Node Down",
            "alert_message": "Node is unreachable",
            "severity": "0",
            "alert_active_id": "100",
            "alert_object_id": "200",
            "alert_id": "300",
            "object_name": "router-01",
            "object_type": "Orion.Nodes",
            "node_name": "router-01",
            "ip_address": "10.0.0.1",
            "triggered_datetime": "2026-02-24T10:30:00Z",
            "acknowledged": "false",
            "acknowledged_by": "",
            "notification_type": "PROBLEM",
        }
        alert = SolarwindsProvider._format_alert(event)
        assert alert.name == "Node Down"
        assert alert.description == "Node is unreachable"
        assert alert.severity == AlertSeverity.CRITICAL.value
        assert alert.status == AlertStatus.FIRING.value
        assert alert.id == "100"
        assert alert.alert_id == "300"
        assert alert.object_name == "router-01"
        assert alert.node_name == "router-01"
        assert alert.ip_address == "10.0.0.1"


# --- Severity mapping correctness ---


class TestSolarwindsSeverityMapping:
    """
    Verify SolarWinds severity mapping matches the official documentation.
    SolarWinds uses INVERTED severity: 0=Critical (most severe), 4=Notice (least).
    """

    def test_severity_0_is_critical(self):
        """SolarWinds 0 = Critical (most severe)."""
        assert SolarwindsProvider.SEVERITY_MAP[0] == AlertSeverity.CRITICAL
        assert SolarwindsProvider.SEVERITY_MAP["0"] == AlertSeverity.CRITICAL

    def test_severity_1_is_high(self):
        """SolarWinds 1 = Serious."""
        assert SolarwindsProvider.SEVERITY_MAP[1] == AlertSeverity.HIGH
        assert SolarwindsProvider.SEVERITY_MAP["1"] == AlertSeverity.HIGH

    def test_severity_2_is_warning(self):
        """SolarWinds 2 = Warning."""
        assert SolarwindsProvider.SEVERITY_MAP[2] == AlertSeverity.WARNING
        assert SolarwindsProvider.SEVERITY_MAP["2"] == AlertSeverity.WARNING

    def test_severity_3_is_info(self):
        """SolarWinds 3 = Informational."""
        assert SolarwindsProvider.SEVERITY_MAP[3] == AlertSeverity.INFO
        assert SolarwindsProvider.SEVERITY_MAP["3"] == AlertSeverity.INFO

    def test_severity_4_is_low(self):
        """SolarWinds 4 = Notice."""
        assert SolarwindsProvider.SEVERITY_MAP[4] == AlertSeverity.LOW
        assert SolarwindsProvider.SEVERITY_MAP["4"] == AlertSeverity.LOW

    def test_named_string_critical(self):
        assert SolarwindsProvider.SEVERITY_MAP["Critical"] == AlertSeverity.CRITICAL

    def test_named_string_serious(self):
        assert SolarwindsProvider.SEVERITY_MAP["Serious"] == AlertSeverity.HIGH

    def test_named_string_warning(self):
        assert SolarwindsProvider.SEVERITY_MAP["Warning"] == AlertSeverity.WARNING

    def test_named_string_informational(self):
        assert SolarwindsProvider.SEVERITY_MAP["Informational"] == AlertSeverity.INFO

    def test_named_string_notice(self):
        assert SolarwindsProvider.SEVERITY_MAP["Notice"] == AlertSeverity.LOW


# --- alerts_mock tests ---


class TestSolarwindsAlertsMock:
    """Verify alerts_mock.py is compatible with simulate_alert()."""

    def test_alerts_mock_format(self):
        from keep.providers.solarwinds_provider.alerts_mock import ALERTS

        assert isinstance(ALERTS, dict)
        for key, value in ALERTS.items():
            assert "payload" in value, f"Key '{key}' missing 'payload'"
            assert isinstance(value["payload"], dict)

    def test_alerts_mock_payloads_format_successfully(self):
        from keep.providers.solarwinds_provider.alerts_mock import ALERTS

        for key, value in ALERTS.items():
            alert = SolarwindsProvider._format_alert(value["payload"])
            assert alert is not None, f"Failed to format alert for key '{key}'"
            assert alert.source == ["solarwinds"]

    def test_alerts_mock_covers_problem_and_recovery(self):
        from keep.providers.solarwinds_provider.alerts_mock import ALERTS

        notification_types = set()
        for value in ALERTS.values():
            notification_types.add(value["payload"].get("notification_type"))
        assert "PROBLEM" in notification_types
        assert "RECOVERY" in notification_types

    def test_alerts_mock_severity_range(self):
        """Mock data should cover multiple severity levels."""
        from keep.providers.solarwinds_provider.alerts_mock import ALERTS

        severities = set()
        for value in ALERTS.values():
            severities.add(value["payload"].get("severity"))
        assert len(severities) >= 3, "Should cover at least 3 severity levels"


# --- Provider metadata tests ---


class TestSolarwindsProviderMetadata:
    def test_display_name(self):
        assert SolarwindsProvider.PROVIDER_DISPLAY_NAME == "SolarWinds"

    def test_tags(self):
        assert "alert" in SolarwindsProvider.PROVIDER_TAGS

    def test_category(self):
        assert "Monitoring" in SolarwindsProvider.PROVIDER_CATEGORY

    def test_fingerprint_fields(self):
        assert SolarwindsProvider.FINGERPRINT_FIELDS is not None
        assert len(SolarwindsProvider.FINGERPRINT_FIELDS) > 0

    def test_scopes_defined(self):
        assert len(SolarwindsProvider.PROVIDER_SCOPES) > 0

    def test_swis_base_path(self):
        assert "InformationService" in SolarwindsProvider.SWIS_BASE_PATH
