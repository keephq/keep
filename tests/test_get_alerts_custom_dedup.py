import hashlib
import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.providers.base.base_provider import BaseProvider


def _make_alert(name, labels=None, fingerprint=None):
    return AlertDto(
        id=name,
        name=name,
        status=AlertStatus.FIRING,
        severity=AlertSeverity.WARNING,
        lastReceived="2025-01-01T00:00:00Z",
        labels=labels or {},
        fingerprint=fingerprint,
        source=["test"],
    )


class _StubProvider(BaseProvider):
    """Concrete stub so we can instantiate BaseProvider for testing."""

    def dispose(self):
        pass

    def validate_config(self):
        pass


def _make_provider(alerts):
    """Create a minimal provider instance that returns canned alerts."""
    provider = object.__new__(_StubProvider)
    provider.provider_id = "test-provider-id"
    provider.provider_type = "prometheus"
    provider.context_manager = MagicMock()
    provider.context_manager.tenant_id = "test-tenant"
    provider.logger = MagicMock()
    provider._get_alerts = MagicMock(return_value=alerts)
    return provider


class TestGetAlertsCustomDedup(unittest.TestCase):
    @patch("keep.providers.base.base_provider.get_custom_deduplication_rule")
    def test_custom_dedup_rule_overwrites_fingerprint(self, mock_get_rule):
        """Pulled alerts should get fingerprints recalculated when a custom dedup rule exists."""
        alert_a = _make_alert(
            "HighCPU",
            labels={"alertname": "HighCPU", "env": "prod"},
            fingerprint="native-fp-1",
        )
        alert_b = _make_alert(
            "HighCPU",
            labels={"alertname": "HighCPU", "env": "staging"},
            fingerprint="native-fp-1",  # same native fingerprint
        )

        rule = MagicMock()
        rule.fingerprint_fields = ["labels.alertname", "labels.env"]
        mock_get_rule.return_value = rule

        provider = _make_provider([alert_a, alert_b])

        with patch(
            "keep.providers.base.base_provider.tracer"
        ) as mock_tracer:
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock()
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock()
            alerts = provider.get_alerts()

        # fingerprints should now differ because env differs
        self.assertNotEqual(alerts[0].fingerprint, alerts[1].fingerprint)

        # verify fingerprint matches expected sha256
        expected_a = hashlib.sha256()
        expected_a.update(b"HighCPU")
        expected_a.update(b"prod")
        self.assertEqual(alerts[0].fingerprint, expected_a.hexdigest())

        expected_b = hashlib.sha256()
        expected_b.update(b"HighCPU")
        expected_b.update(b"staging")
        self.assertEqual(alerts[1].fingerprint, expected_b.hexdigest())

    @patch("keep.providers.base.base_provider.get_custom_deduplication_rule")
    def test_no_custom_rule_keeps_original_fingerprint(self, mock_get_rule):
        """Without a custom dedup rule, pulled alerts keep their original fingerprint."""
        alert = _make_alert(
            "DiskFull",
            labels={"alertname": "DiskFull"},
            fingerprint="original-fp",
        )

        mock_get_rule.return_value = None

        provider = _make_provider([alert])

        with patch(
            "keep.providers.base.base_provider.tracer"
        ) as mock_tracer:
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock()
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock()
            alerts = provider.get_alerts()

        self.assertEqual(alerts[0].fingerprint, "original-fp")

    @patch("keep.providers.base.base_provider.get_custom_deduplication_rule")
    def test_custom_dedup_with_dot_notation_fields(self, mock_get_rule):
        """Custom dedup should support dot-notation to access nested dict fields."""
        alert = _make_alert(
            "NodeDown",
            labels={"alertname": "NodeDown", "env_dc": "us-east", "group": "infra"},
        )

        rule = MagicMock()
        rule.fingerprint_fields = [
            "labels.alertname",
            "labels.env_dc",
            "labels.group",
        ]
        mock_get_rule.return_value = rule

        provider = _make_provider([alert])

        with patch(
            "keep.providers.base.base_provider.tracer"
        ) as mock_tracer:
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock()
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock()
            alerts = provider.get_alerts()

        expected = hashlib.sha256()
        expected.update(b"NodeDown")
        expected.update(b"us-east")
        expected.update(b"infra")
        self.assertEqual(alerts[0].fingerprint, expected.hexdigest())


if __name__ == "__main__":
    unittest.main()
