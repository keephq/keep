"""
Unit tests for the Kapacitor provider.

Tests cover:
  - Webhook payload parsing (_format_alert) for all alert levels
  - Severity and status mapping (CRITICAL, WARNING, INFO, OK)
  - Tag extraction into labels
  - Resolved alert detection
  - Pull-mode event formatting (_format_event)
  - Edge cases: missing fields, empty series, unknown levels
"""

import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.kapacitor_provider.kapacitor_provider import KapacitorProvider
from keep.providers.models.provider_config import ProviderConfig


def _make_provider() -> KapacitorProvider:
    mock_context = MagicMock(spec=ContextManager)
    mock_context.tenant_id = "test"
    mock_context.workflow_id = None
    config = ProviderConfig(
        authentication={"kapacitor_url": "http://kapacitor:9092"},
        name="kap-test",
        description="Test",
    )
    return KapacitorProvider(
        context_manager=mock_context, provider_id="kap-1", config=config
    )


# ---------------------------------------------------------------------------
# Webhook _format_alert tests
# ---------------------------------------------------------------------------


class TestKapacitorWebhookParsing(unittest.TestCase):
    def _make_payload(self, **overrides) -> dict:
        base = {
            "id": "cpu_alert:host=web01",
            "message": "CPU is CRITICAL on web01",
            "details": "",
            "time": "2026-03-29T12:34:56.789Z",
            "duration": 60000000000,
            "level": "CRITICAL",
            "data": {
                "series": [
                    {
                        "name": "cpu",
                        "tags": {"host": "web01", "cpu": "cpu-total"},
                        "columns": ["time", "cpu_usage_idle"],
                        "values": [["2026-03-29T12:34:56Z", 4.0]],
                    }
                ]
            },
            "previousLevel": "OK",
            "recoverable": True,
        }
        base.update(overrides)
        return base

    def test_returns_alert_dto(self):
        result = KapacitorProvider._format_alert(self._make_payload())
        self.assertIsInstance(result, AlertDto)

    def test_id_preserved(self):
        result = KapacitorProvider._format_alert(self._make_payload())
        self.assertEqual(result.id, "cpu_alert:host=web01")

    def test_message_as_description(self):
        payload = self._make_payload(message="My custom alert message")
        result = KapacitorProvider._format_alert(payload)
        self.assertEqual(result.description, "My custom alert message")

    def test_source_is_kapacitor(self):
        result = KapacitorProvider._format_alert(self._make_payload())
        self.assertIn("kapacitor", result.source)

    def test_time_preserved_as_last_received(self):
        result = KapacitorProvider._format_alert(self._make_payload())
        self.assertEqual(result.lastReceived, "2026-03-29T12:34:56.789Z")

    def test_missing_time_gives_none(self):
        payload = self._make_payload()
        del payload["time"]
        result = KapacitorProvider._format_alert(payload)
        self.assertIsNone(result.lastReceived)

    # ------------------------------------------------------------------
    # Severity mapping
    # ------------------------------------------------------------------

    def test_critical_severity(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="CRITICAL"))
        self.assertEqual(result.severity, AlertSeverity.CRITICAL)

    def test_warning_severity(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="WARNING"))
        self.assertEqual(result.severity, AlertSeverity.WARNING)

    def test_info_severity(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="INFO"))
        self.assertEqual(result.severity, AlertSeverity.INFO)

    def test_ok_severity_is_low(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="OK"))
        self.assertEqual(result.severity, AlertSeverity.LOW)

    def test_unknown_level_defaults_high(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="UNKNOWN"))
        self.assertEqual(result.severity, AlertSeverity.HIGH)

    # ------------------------------------------------------------------
    # Status mapping
    # ------------------------------------------------------------------

    def test_critical_status_is_firing(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="CRITICAL"))
        self.assertEqual(result.status, AlertStatus.FIRING)

    def test_warning_status_is_firing(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="WARNING"))
        self.assertEqual(result.status, AlertStatus.FIRING)

    def test_ok_status_is_resolved(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="OK"))
        self.assertEqual(result.status, AlertStatus.RESOLVED)

    def test_info_status_is_firing(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="INFO"))
        self.assertEqual(result.status, AlertStatus.FIRING)

    # ------------------------------------------------------------------
    # Labels and tags
    # ------------------------------------------------------------------

    def test_tags_in_labels(self):
        result = KapacitorProvider._format_alert(self._make_payload())
        self.assertEqual(result.labels.get("host"), "web01")
        self.assertEqual(result.labels.get("cpu"), "cpu-total")

    def test_measurement_in_labels(self):
        result = KapacitorProvider._format_alert(self._make_payload())
        self.assertEqual(result.labels.get("measurement"), "cpu")

    def test_level_in_labels(self):
        result = KapacitorProvider._format_alert(self._make_payload(level="WARNING"))
        self.assertEqual(result.labels.get("level"), "WARNING")

    def test_previous_level_in_labels(self):
        result = KapacitorProvider._format_alert(self._make_payload(previousLevel="INFO"))
        self.assertEqual(result.labels.get("previousLevel"), "INFO")

    def test_empty_series_no_tag_labels(self):
        payload = self._make_payload()
        payload["data"] = {"series": []}
        result = KapacitorProvider._format_alert(payload)
        self.assertIsInstance(result, AlertDto)
        self.assertNotIn("host", result.labels)

    def test_missing_data_key(self):
        payload = self._make_payload()
        del payload["data"]
        result = KapacitorProvider._format_alert(payload)
        self.assertIsInstance(result, AlertDto)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_id_fallback_to_message(self):
        payload = self._make_payload(id="", message="Alert fired for svc-x")
        result = KapacitorProvider._format_alert(payload)
        # name should be the first 80 chars of message
        self.assertIn("Alert fired for svc-x", result.name)

    def test_disk_alert_multiple_tags(self):
        payload = self._make_payload()
        payload["id"] = "disk_alert:host=storage01,path=/data"
        payload["data"]["series"][0]["tags"] = {
            "host": "storage01",
            "device": "sda1",
            "path": "/data",
        }
        payload["data"]["series"][0]["name"] = "disk"
        result = KapacitorProvider._format_alert(payload)
        self.assertEqual(result.labels["host"], "storage01")
        self.assertEqual(result.labels["path"], "/data")
        self.assertEqual(result.labels["measurement"], "disk")


# ---------------------------------------------------------------------------
# Pull mode _format_event tests
# ---------------------------------------------------------------------------


class TestKapacitorPullMode(unittest.TestCase):
    def setUp(self):
        self.provider = _make_provider()

    def _make_event(self, **overrides) -> dict:
        base = {
            "id": "cpu_alert:host=web01",
            "state": {
                "level": "CRITICAL",
                "message": "CPU is CRITICAL on web01",
                "timestamp": "2026-03-29T12:34:56Z",
            },
        }
        base.update(overrides)
        return base

    def test_basic_event_parse(self):
        event = self._make_event()
        dto = self.provider._format_event(event, "cpu_topic")
        self.assertIsInstance(dto, AlertDto)
        self.assertEqual(dto.id, "cpu_alert:host=web01")

    def test_topic_in_labels(self):
        event = self._make_event()
        dto = self.provider._format_event(event, "cpu_topic")
        self.assertEqual(dto.labels["topic"], "cpu_topic")

    def test_level_in_labels(self):
        event = self._make_event()
        dto = self.provider._format_event(event, "cpu_topic")
        self.assertEqual(dto.labels["level"], "CRITICAL")

    def test_severity_critical(self):
        event = self._make_event()
        dto = self.provider._format_event(event, "t")
        self.assertEqual(dto.severity, AlertSeverity.CRITICAL)

    def test_severity_warning(self):
        base_event = self._make_event()
        base_event["state"]["level"] = "WARNING"
        dto = self.provider._format_event(base_event, "t")
        self.assertEqual(dto.severity, AlertSeverity.WARNING)

    def test_ok_level_is_resolved(self):
        base_event = self._make_event()
        base_event["state"]["level"] = "OK"
        dto = self.provider._format_event(base_event, "t")
        self.assertEqual(dto.status, AlertStatus.RESOLVED)

    def test_timestamp_preserved(self):
        event = self._make_event()
        dto = self.provider._format_event(event, "t")
        self.assertEqual(dto.lastReceived, "2026-03-29T12:34:56Z")

    def test_missing_timestamp(self):
        event = self._make_event()
        event["state"].pop("timestamp", None)
        dto = self.provider._format_event(event, "t")
        self.assertIsNone(dto.lastReceived)

    def test_source_is_kapacitor(self):
        event = self._make_event()
        dto = self.provider._format_event(event, "t")
        self.assertIn("kapacitor", dto.source)


# ---------------------------------------------------------------------------
# Provider config tests
# ---------------------------------------------------------------------------


class TestKapacitorProviderConfig(unittest.TestCase):
    def test_validate_config(self):
        provider = _make_provider()
        self.assertEqual(
            str(provider.authentication_config.kapacitor_url),
            "http://kapacitor:9092/",
        )

    def test_no_auth_credentials(self):
        provider = _make_provider()
        self.assertIsNone(provider.authentication_config.username)
        self.assertIsNone(provider.authentication_config.password)

    def test_base_url_strips_trailing_slash(self):
        provider = _make_provider()
        self.assertEqual(provider._base_url(), "http://kapacitor:9092")

    def test_session_no_auth(self):
        provider = _make_provider()
        session = provider._get_session()
        self.assertIsNone(session.auth)

    def test_session_with_auth(self):
        mock_ctx = MagicMock(spec=ContextManager)
        mock_ctx.tenant_id = "t"
        mock_ctx.workflow_id = None
        config = ProviderConfig(
            authentication={
                "kapacitor_url": "http://kap:9092",
                "username": "admin",
                "password": "secret",
            },
            name="kap2",
            description="",
        )
        provider = KapacitorProvider(
            context_manager=mock_ctx, provider_id="kap-2", config=config
        )
        session = provider._get_session()
        self.assertEqual(session.auth, ("admin", "secret"))

    def test_validate_scopes_ok(self):
        provider = _make_provider()
        with patch("requests.Session.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=204)
            result = provider.validate_scopes()
        self.assertTrue(result["connectivity"])

    def test_validate_scopes_error(self):
        provider = _make_provider()
        with patch("requests.Session.get", side_effect=ConnectionError("refused")):
            result = provider.validate_scopes()
        self.assertIn("refused", result["connectivity"])

    def test_validate_scopes_non_200(self):
        provider = _make_provider()
        with patch("requests.Session.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=401, text="Unauthorized")
            result = provider.validate_scopes()
        self.assertIn("401", result["connectivity"])


# ---------------------------------------------------------------------------
# Pull _get_alerts tests
# ---------------------------------------------------------------------------


class TestKapacitorGetAlerts(unittest.TestCase):
    def setUp(self):
        self.provider = _make_provider()

    def test_get_alerts_returns_dtos(self):
        topics_resp = MagicMock(status_code=200)
        topics_resp.json.return_value = {"topics": [{"id": "cpu_topic"}]}
        events_resp = MagicMock(status_code=200)
        events_resp.json.return_value = {
            "events": [
                {
                    "id": "cpu_alert:host=web01",
                    "state": {
                        "level": "CRITICAL",
                        "message": "CPU critical",
                        "timestamp": "2026-03-29T12:00:00Z",
                    },
                }
            ]
        }
        with patch.object(self.provider._get_session().__class__, "get") as mock_get:
            mock_get.side_effect = [topics_resp, events_resp]
            with patch.object(self.provider, "_get_session", return_value=MagicMock(
                get=MagicMock(side_effect=[topics_resp, events_resp])
            )):
                alerts = self.provider._get_alerts()
        self.assertIsInstance(alerts, list)

    def test_get_alerts_empty_topics(self):
        topics_resp = MagicMock(status_code=200)
        topics_resp.json.return_value = {"topics": []}
        with patch.object(self.provider, "_get_session", return_value=MagicMock(
            get=MagicMock(return_value=topics_resp)
        )):
            alerts = self.provider._get_alerts()
        self.assertEqual(alerts, [])

    def test_get_alerts_returns_empty_on_connection_error(self):
        mock_session = MagicMock()
        mock_session.get.side_effect = ConnectionError("refused")
        with patch.object(self.provider, "_get_session", return_value=mock_session):
            alerts = self.provider._get_alerts()
        self.assertEqual(alerts, [])


# ---------------------------------------------------------------------------
# Alerts mock sanity tests
# ---------------------------------------------------------------------------


class TestKapacitorAlertsMock(unittest.TestCase):
    def test_all_mocks_parseable(self):
        from keep.providers.kapacitor_provider.alerts_mock import ALERTS

        for name, alert_def in ALERTS.items():
            payload = alert_def["payload"]
            result = KapacitorProvider._format_alert(payload)
            self.assertIsInstance(result, AlertDto, f"Expected AlertDto for mock '{name}'")

    def test_resolved_mock_has_resolved_status(self):
        from keep.providers.kapacitor_provider.alerts_mock import ALERTS

        payload = ALERTS["AlertResolved"]["payload"]
        result = KapacitorProvider._format_alert(payload)
        self.assertEqual(result.status, AlertStatus.RESOLVED)

    def test_critical_mock_has_critical_severity(self):
        from keep.providers.kapacitor_provider.alerts_mock import ALERTS

        payload = ALERTS["CpuCritical"]["payload"]
        result = KapacitorProvider._format_alert(payload)
        self.assertEqual(result.severity, AlertSeverity.CRITICAL)

    def test_warning_mock_has_warning_severity(self):
        from keep.providers.kapacitor_provider.alerts_mock import ALERTS

        payload = ALERTS["MemoryWarning"]["payload"]
        result = KapacitorProvider._format_alert(payload)
        self.assertEqual(result.severity, AlertSeverity.WARNING)


if __name__ == "__main__":
    unittest.main()
