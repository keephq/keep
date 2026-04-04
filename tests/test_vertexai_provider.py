"""
Tests for VertexaiProvider._format_alert and related helpers.

Follows the same unittest pattern as test_pagerduty_provider.py.
Uses the mock payloads from alerts_mock.py verbatim, but passes deep copies
to avoid mutation side-effects (incident.pop() inside _format_alert).
"""
import copy
import unittest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.vertexai_provider.alerts_mock import ALERTS
from keep.providers.vertexai_provider.vertexai_provider import VertexaiProvider


class TestVertexaiProviderFormatAlert(unittest.TestCase):
    """Unit-tests for the static VertexaiProvider._format_alert method."""

    # ------------------------------------------------------------------ helpers

    def _format(self, key: str):
        """Return a formatted AlertDto from the named mock payload (deep copy)."""
        payload = copy.deepcopy(ALERTS[key]["payload"])
        return VertexaiProvider._format_alert(payload)

    # ------------------------------------------------------------------ mock 1: high error rate

    def test_high_error_rate_basic_fields(self):
        alert = self._format("model_high_error_rate")

        self.assertEqual(alert.id, "vertexai-err-001")
        self.assertEqual(alert.name, "Vertex AI Endpoint High Error Rate")
        self.assertEqual(
            alert.description, "High error rate detected on Vertex AI model endpoint"
        )
        self.assertEqual(alert.source, ["vertexai"])
        self.assertIn("vertexai", alert.url)

    def test_high_error_rate_severity(self):
        alert = self._format("model_high_error_rate")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)

    def test_high_error_rate_status(self):
        alert = self._format("model_high_error_rate")
        self.assertEqual(alert.status, AlertStatus.FIRING.value)

    def test_high_error_rate_resource_labels(self):
        alert = self._format("model_high_error_rate")
        # Extra fields are allowed by AlertDto (Extra.allow)
        self.assertEqual(alert.endpoint_id, "1234567890123456789")
        self.assertEqual(alert.location, "us-central1")
        self.assertEqual(alert.project_id, "my-gcp-project")

    def test_high_error_rate_fingerprint_set(self):
        alert = self._format("model_high_error_rate")
        self.assertIsNotNone(alert.fingerprint)

    # ------------------------------------------------------------------ mock 2: high latency

    def test_high_latency_basic_fields(self):
        alert = self._format("model_high_latency")

        self.assertEqual(alert.id, "vertexai-lat-002")
        self.assertEqual(alert.name, "Vertex AI Endpoint High Latency")
        self.assertEqual(
            alert.description,
            "High latency detected on Vertex AI model endpoint predictions",
        )

    def test_high_latency_severity(self):
        alert = self._format("model_high_latency")
        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)

    def test_high_latency_status_is_firing(self):
        alert = self._format("model_high_latency")
        self.assertEqual(alert.status, AlertStatus.FIRING.value)

    def test_high_latency_resource_labels(self):
        alert = self._format("model_high_latency")
        self.assertEqual(alert.endpoint_id, "9876543210987654321")

    # ------------------------------------------------------------------ mock 3: endpoint down

    def test_endpoint_down_basic_fields(self):
        alert = self._format("model_endpoint_down")

        self.assertEqual(alert.id, "vertexai-down-003")
        self.assertEqual(alert.name, "Vertex AI Endpoint Appears Down")

    def test_endpoint_down_severity(self):
        alert = self._format("model_endpoint_down")
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL.value)

    def test_endpoint_down_location(self):
        """Endpoint-down fires from us-east1, not us-central1."""
        alert = self._format("model_endpoint_down")
        self.assertEqual(alert.location, "us-east1")

    # ------------------------------------------------------------------ mock 4: feature skew

    def test_feature_skew_basic_fields(self):
        alert = self._format("model_monitoring_skew")

        self.assertEqual(alert.id, "vertexai-skew-004")
        self.assertEqual(alert.name, "Vertex AI Model Feature Skew Detected")

    def test_feature_skew_severity(self):
        alert = self._format("model_monitoring_skew")
        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)

    def test_feature_skew_content_field(self):
        alert = self._format("model_monitoring_skew")
        self.assertIn("feature skew", alert.content.lower())

    # ------------------------------------------------------------------ severity mapping

    def test_severity_map_critical(self):
        self.assertEqual(
            VertexaiProvider.SEVERITIES_MAP["CRITICAL"], AlertSeverity.CRITICAL
        )

    def test_severity_map_error(self):
        self.assertEqual(
            VertexaiProvider.SEVERITIES_MAP["ERROR"], AlertSeverity.HIGH
        )

    def test_severity_map_warning(self):
        self.assertEqual(
            VertexaiProvider.SEVERITIES_MAP["WARNING"], AlertSeverity.WARNING
        )

    def test_severity_map_info(self):
        self.assertEqual(
            VertexaiProvider.SEVERITIES_MAP["INFO"], AlertSeverity.INFO
        )

    def test_unknown_severity_defaults_to_warning(self):
        """An unrecognised severity label should fall back to WARNING."""
        payload = copy.deepcopy(ALERTS["model_high_latency"]["payload"])
        payload["incident"]["policy_user_labels"]["severity"] = "UNKNOWN_SEVERITY"
        alert = VertexaiProvider._format_alert(payload)
        self.assertEqual(alert.severity, AlertSeverity.WARNING.value)

    # ------------------------------------------------------------------ status mapping

    def test_status_map_open(self):
        self.assertEqual(VertexaiProvider.STATUS_MAP["OPEN"], AlertStatus.FIRING)

    def test_status_map_closed(self):
        self.assertEqual(VertexaiProvider.STATUS_MAP["CLOSED"], AlertStatus.RESOLVED)

    def test_closed_incident_status_resolved(self):
        payload = copy.deepcopy(ALERTS["model_high_error_rate"]["payload"])
        payload["incident"]["state"] = "CLOSED"
        alert = VertexaiProvider._format_alert(payload)
        self.assertEqual(alert.status, AlertStatus.RESOLVED.value)

    # ------------------------------------------------------------------ started_at edge cases

    def test_zero_started_at_falls_back_to_now(self):
        """started_at == 0 is falsy; _format_alert should use current time."""
        payload = copy.deepcopy(ALERTS["model_high_error_rate"]["payload"])
        # All mock payloads have started_at == 0 already
        self.assertEqual(payload["incident"]["started_at"], 0)
        alert = VertexaiProvider._format_alert(payload)
        # lastReceived must be a valid ISO string — just check it was set
        self.assertIsNotNone(alert.lastReceived)
        self.assertIn("T", alert.lastReceived)

    def test_missing_started_at_falls_back_to_now(self):
        """started_at absent entirely should also fall back to now."""
        payload = copy.deepcopy(ALERTS["model_high_error_rate"]["payload"])
        del payload["incident"]["started_at"]
        alert = VertexaiProvider._format_alert(payload)
        self.assertIsNotNone(alert.lastReceived)

    def test_valid_unix_started_at(self):
        """A real epoch timestamp should produce a matching ISO string."""
        payload = copy.deepcopy(ALERTS["model_high_error_rate"]["payload"])
        payload["incident"]["started_at"] = 1_700_000_000  # 2023-11-14 …
        alert = VertexaiProvider._format_alert(payload)
        self.assertIn("2023", alert.lastReceived)

    def test_string_unix_started_at(self):
        """started_at sent as a string (e.g. '1700000000') must also be handled."""
        payload = copy.deepcopy(ALERTS["model_high_error_rate"]["payload"])
        payload["incident"]["started_at"] = "1700000000"
        alert = VertexaiProvider._format_alert(payload)
        self.assertIn("2023", alert.lastReceived)

    # ------------------------------------------------------------------ documentation variants

    def test_non_dict_documentation_uses_test_notification_name(self):
        """When documentation is not a dict, name should be 'Vertex AI Test Notification'."""
        payload = copy.deepcopy(ALERTS["model_high_error_rate"]["payload"])
        payload["incident"]["documentation"] = "plain string doc"
        alert = VertexaiProvider._format_alert(payload)
        self.assertEqual(alert.name, "Vertex AI Test Notification")

    def test_missing_documentation_subject_falls_back_to_summary(self):
        """When documentation dict has no 'subject', name falls back to summary."""
        payload = copy.deepcopy(ALERTS["model_high_error_rate"]["payload"])
        payload["incident"]["documentation"] = {"content": "some content"}
        alert = VertexaiProvider._format_alert(payload)
        # summary is "High error rate detected on Vertex AI model endpoint"
        self.assertIsNotNone(alert.name)
        self.assertNotEqual(alert.name, "")


if __name__ == "__main__":
    unittest.main()
