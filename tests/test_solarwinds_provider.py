from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.solarwinds_provider.solarwinds_provider import SolarwindsProvider


class TestSolarwindsProviderFormatAlert:
    def test_critical_active_alert(self):
        event = {
            "AlertObjectID": "123456",
            "AlertName": "High CPU Usage",
            "Severity": "Critical",
            "IsAcknowledged": False,
            "IsActive": True,
        }

        alert = SolarwindsProvider._format_alert(event)

        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.CRITICAL

    def test_warning_acknowledged_alert(self):
        event = {
            "AlertObjectID": "123457",
            "AlertName": "Memory warning",
            "Severity": "Warning",
            "IsAcknowledged": "true",
            "IsActive": "1",
        }

        alert = SolarwindsProvider._format_alert(event)

        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.severity == AlertSeverity.WARNING

    def test_inactive_alert_is_resolved(self):
        event = {
            "AlertObjectID": "123458",
            "AlertName": "Disk alert",
            "Severity": "Critical",
            "IsAcknowledged": False,
            "IsActive": False,
        }

        alert = SolarwindsProvider._format_alert(event)

        assert alert.status == AlertStatus.RESOLVED

    def test_fallback_id_and_name_when_missing_fields(self):
        alert = SolarwindsProvider._format_alert({})

        assert alert.id == "unknown-host:solarwinds-alert"
        assert alert.name == "SolarWinds alert"

    def test_missing_is_active_defaults_to_firing(self):
        event = {
            "AlertObjectID": "123459",
            "AlertName": "Packet loss",
            "Severity": "Major",
        }

        alert = SolarwindsProvider._format_alert(event)

        assert alert.status == AlertStatus.FIRING
        assert alert.severity == AlertSeverity.HIGH
