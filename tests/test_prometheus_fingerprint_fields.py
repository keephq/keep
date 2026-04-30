"""
Tests for Prometheus provider custom fingerprint fields (issue #5370).

The bug: Prometheus provider ignores custom fingerprint_fields configured in
deduplication rules. All alerts with the same alertname get the same fingerprint
regardless of other label values.

Root cause: Pulled alerts (already AlertDto) were passed through process_event
without applying the custom deduplication rule's fingerprint calculation.
"""

import unittest

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.base.base_provider import BaseProvider
from keep.providers.prometheus_provider.prometheus_provider import PrometheusProvider


class TestPrometheusFingerprint(unittest.TestCase):
    """Test that custom fingerprint fields produce unique fingerprints."""

    def _make_alert(self, alertname, env_dc="prod", group="infra"):
        """Create a Prometheus-like AlertDto with labels."""
        return AlertDto(
            id=alertname,
            name=alertname,
            description="test",
            severity=AlertSeverity.WARNING,
            status=AlertStatus.FIRING,
            source=["prometheus"],
            labels={
                "alertname": alertname,
                "env_dc": env_dc,
                "group": group,
            },
            fingerprint=None,
        )

    def test_default_fingerprint_is_name(self):
        """Without custom fields, fingerprint should be alert.name."""
        alert = self._make_alert("NodeLowDiskSpace4Hours")
        fp = BaseProvider.get_alert_fingerprint(alert, fingerprint_fields=[])
        self.assertEqual(fp, "NodeLowDiskSpace4Hours")

    def test_custom_fields_produce_unique_fingerprints(self):
        """With custom fingerprint_fields, different label values → different fingerprints."""
        alert1 = self._make_alert("NodeLowDiskSpace4Hours", env_dc="prod-us1", group="infra")
        alert2 = self._make_alert("NodeLowDiskSpace4Hours", env_dc="prod-eu1", group="infra")
        alert3 = self._make_alert("NodeLowDiskSpace4Hours", env_dc="prod-us1", group="storage")

        fields = ["labels.alertname", "labels.env_dc", "labels.group"]

        fp1 = BaseProvider.get_alert_fingerprint(alert1, fingerprint_fields=fields)
        fp2 = BaseProvider.get_alert_fingerprint(alert2, fingerprint_fields=fields)
        fp3 = BaseProvider.get_alert_fingerprint(alert3, fingerprint_fields=fields)

        # All should be different because label values differ
        self.assertNotEqual(fp1, fp2)
        self.assertNotEqual(fp1, fp3)
        self.assertNotEqual(fp2, fp3)

        # All should be hex hashes, not plain names
        self.assertNotEqual(fp1, "NodeLowDiskSpace4Hours")
        self.assertEqual(len(fp1), 64)  # sha256 hex digest

    def test_same_labels_same_fingerprint(self):
        """Same label values should produce the same fingerprint."""
        alert1 = self._make_alert("TestAlert", env_dc="prod", group="app")
        alert2 = self._make_alert("TestAlert", env_dc="prod", group="app")

        fields = ["labels.alertname", "labels.env_dc", "labels.group"]

        fp1 = BaseProvider.get_alert_fingerprint(alert1, fingerprint_fields=fields)
        fp2 = BaseProvider.get_alert_fingerprint(alert2, fingerprint_fields=fields)

        self.assertEqual(fp1, fp2)

    def test_format_alert_preserves_labels(self):
        """_format_alert should preserve labels in the AlertDto for fingerprint calculation."""
        event = {
            "status": "firing",
            "labels": {
                "alertname": "HighCPU",
                "env_dc": "staging",
                "group": "compute",
                "severity": "warning",
            },
            "annotations": {"description": "CPU > 90%"},
        }

        alerts = PrometheusProvider._format_alert(event)
        alert = alerts[0]

        # Labels should be accessible for fingerprint traversal
        self.assertIn("alertname", alert.labels)
        self.assertIn("env_dc", alert.labels)
        self.assertIn("group", alert.labels)


if __name__ == "__main__":
    unittest.main()
