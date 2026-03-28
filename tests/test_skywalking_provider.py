"""
Unit tests for the Apache SkyWalking provider.

Tests cover:
  - Webhook payload parsing (_format_alert) for all alarm scopes
  - Pull-mode alarm record formatting (_format_alarm_record)
  - Severity and status mapping
  - Edge cases (missing fields, empty payloads, malformed timestamps)
"""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.skywalking_provider.skywalking_provider import SkywalkingProvider


def _make_provider() -> SkywalkingProvider:
    """Create a SkywalkingProvider instance with a minimal mock config."""
    mock_context = MagicMock(spec=ContextManager)
    mock_context.tenant_id = "test-tenant"
    mock_context.workflow_id = None
    config = ProviderConfig(
        authentication={"oap_url": "http://skywalking-oap:12800"},
        name="skywalking-test",
        description="Test instance",
    )
    return SkywalkingProvider(
        context_manager=mock_context,
        provider_id="sw-test",
        config=config,
    )


# ---------------------------------------------------------------------------
# Webhook (_format_alert) tests
# ---------------------------------------------------------------------------


class TestSkywalkingWebhookParsing(unittest.TestCase):
    """Tests for _format_alert static method (webhook mode)."""

    def _make_alarm(self, **overrides) -> dict:
        base = {
            "scope": "Service",
            "name": "payment-service",
            "id0": "abc123",
            "id1": "",
            "ruleName": "service_resp_time_rule",
            "alarmMessage": "Response time of service payment-service is more than 1000ms",
            "startTime": 1743200000000,
            "tags": [],
            "events": [],
        }
        base.update(overrides)
        return base

    def test_list_payload_returns_list_of_dtos(self):
        """SkyWalking posts a JSON array; _format_alert must return a list."""
        payload = [self._make_alarm(), self._make_alarm(name="order-service")]
        result = SkywalkingProvider._format_alert(payload)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_alarms_key_payload(self):
        """Payloads wrapped in {'alarms': [...]} are also accepted."""
        payload = {"alarms": [self._make_alarm()]}
        result = SkywalkingProvider._format_alert(payload)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_single_alarm_dict(self):
        """A bare alarm dict is returned as a single AlertDto."""
        alarm = self._make_alarm()
        result = SkywalkingProvider._format_alert(alarm)
        self.assertIsInstance(result, AlertDto)

    def test_id_field_set(self):
        alarm = self._make_alarm()
        result = SkywalkingProvider._format_alert(alarm)
        self.assertIsInstance(result, AlertDto)
        self.assertEqual(result.id, "abc123")

    def test_rule_name_used_as_id_fallback(self):
        alarm = self._make_alarm()
        del alarm["id0"]
        alarm.pop("id", None)
        result = SkywalkingProvider._format_alert(alarm)
        # When 'id' and 'id0' are absent, ruleName is used
        self.assertEqual(result.id, "service_resp_time_rule")

    def test_name_from_name_field(self):
        alarm = self._make_alarm(name="my-service")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.name, "my-service")

    def test_name_falls_back_to_rule_name(self):
        alarm = self._make_alarm()
        alarm["name"] = ""
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.name, "service_resp_time_rule")

    def test_description_from_alarm_message(self):
        alarm = self._make_alarm(alarmMessage="Custom alarm message")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.description, "Custom alarm message")

    def test_status_is_firing(self):
        alarm = self._make_alarm()
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.status, AlertStatus.FIRING)

    def test_source_is_skywalking(self):
        alarm = self._make_alarm()
        result = SkywalkingProvider._format_alert(alarm)
        self.assertIn("skywalking", result.source)

    # ------------------------------------------------------------------
    # Severity mapping tests
    # ------------------------------------------------------------------

    def test_severity_critical_from_rule_name(self):
        alarm = self._make_alarm(ruleName="critical_cpu_rule")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.severity, AlertSeverity.CRITICAL)

    def test_severity_warning_from_message(self):
        alarm = self._make_alarm(alarmMessage="Warning: latency is high")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.severity, AlertSeverity.WARNING)

    def test_severity_info_from_message(self):
        alarm = self._make_alarm(alarmMessage="Info: service started")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.severity, AlertSeverity.INFO)

    def test_severity_high_from_error_message(self):
        alarm = self._make_alarm(alarmMessage="Error rate exceeded threshold")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.severity, AlertSeverity.HIGH)

    def test_severity_warn_alias(self):
        alarm = self._make_alarm(alarmMessage="warn: disk usage at 85%")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.severity, AlertSeverity.WARNING)

    def test_default_severity_is_high(self):
        """When no severity keyword appears, default to HIGH."""
        alarm = self._make_alarm(
            ruleName="mysterious_rule",
            alarmMessage="Something happened",
        )
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.severity, AlertSeverity.HIGH)

    # ------------------------------------------------------------------
    # Timestamp tests
    # ------------------------------------------------------------------

    def test_start_time_parsed_correctly(self):
        # 1743200000000 ms = 2025-03-28 20:53:20 UTC
        alarm = self._make_alarm(startTime=1743200000000)
        result = SkywalkingProvider._format_alert(alarm)
        self.assertIsNotNone(result.lastReceived)
        self.assertIn("2025-03-28", result.lastReceived)

    def test_missing_start_time(self):
        alarm = self._make_alarm()
        del alarm["startTime"]
        result = SkywalkingProvider._format_alert(alarm)
        self.assertIsNone(result.lastReceived)

    def test_invalid_start_time(self):
        alarm = self._make_alarm(startTime="not-a-number")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertIsNone(result.lastReceived)

    # ------------------------------------------------------------------
    # Labels tests
    # ------------------------------------------------------------------

    def test_labels_contain_scope(self):
        alarm = self._make_alarm(scope="ServiceInstance")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.labels.get("scope"), "ServiceInstance")

    def test_labels_contain_rule_name(self):
        alarm = self._make_alarm(ruleName="my_rule")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.labels.get("ruleName"), "my_rule")

    def test_tags_included_in_labels(self):
        alarm = self._make_alarm(
            tags=[{"key": "env", "value": "production"}, {"key": "region", "value": "us-east-1"}]
        )
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.labels.get("env"), "production")
        self.assertEqual(result.labels.get("region"), "us-east-1")

    def test_id0_in_labels(self):
        alarm = self._make_alarm(id0="svc_id_001")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.labels.get("id0"), "svc_id_001")

    def test_empty_tags(self):
        alarm = self._make_alarm(tags=[])
        result = SkywalkingProvider._format_alert(alarm)
        self.assertIsInstance(result.labels, dict)

    # ------------------------------------------------------------------
    # Scope-specific tests
    # ------------------------------------------------------------------

    def test_service_scope_alarm(self):
        alarm = self._make_alarm(scope="Service", name="checkout-service")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.name, "checkout-service")
        self.assertEqual(result.labels["scope"], "Service")

    def test_service_instance_scope_alarm(self):
        alarm = self._make_alarm(
            scope="ServiceInstance",
            name="auth-service#192.168.1.5-pid:42@auth-server",
        )
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.name, "auth-service#192.168.1.5-pid:42@auth-server")
        self.assertEqual(result.labels["scope"], "ServiceInstance")

    def test_endpoint_scope_alarm(self):
        alarm = self._make_alarm(
            scope="Endpoint",
            name="POST:/api/v1/checkout in checkout-service",
        )
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.name, "POST:/api/v1/checkout in checkout-service")

    def test_database_scope_alarm(self):
        alarm = self._make_alarm(scope="Database", name="mysql-prod")
        result = SkywalkingProvider._format_alert(alarm)
        self.assertEqual(result.labels["scope"], "Database")

    def test_multiple_alarms_in_list(self):
        alarms = [
            self._make_alarm(name="svc-a", ruleName="rule_a"),
            self._make_alarm(name="svc-b", ruleName="rule_b"),
            self._make_alarm(name="svc-c", ruleName="rule_c"),
        ]
        result = SkywalkingProvider._format_alert(alarms)
        self.assertEqual(len(result), 3)
        names = {a.name for a in result}
        self.assertEqual(names, {"svc-a", "svc-b", "svc-c"})


# ---------------------------------------------------------------------------
# Pull mode (_format_alarm_record) tests
# ---------------------------------------------------------------------------


class TestSkywalkingPullMode(unittest.TestCase):
    """Tests for the internal _format_alarm_record method (pull / GraphQL mode)."""

    def setUp(self):
        self.provider = _make_provider()

    def _make_record(self, **overrides) -> dict:
        base = {
            "id": "gql-alarm-001",
            "message": "Response time of service api-gateway is more than 1000ms in 3 minutes",
            "startTime": 1743200000000,
            "scope": "Service",
            "scopeId": "YXBpLWdhdGV3YXk=.1",
            "name": "api-gateway",
        }
        base.update(overrides)
        return base

    def test_basic_record_parsing(self):
        record = self._make_record()
        dto = self.provider._format_alarm_record(record)
        self.assertIsInstance(dto, AlertDto)
        self.assertEqual(dto.id, "gql-alarm-001")
        self.assertEqual(dto.name, "api-gateway")

    def test_status_is_firing(self):
        record = self._make_record()
        dto = self.provider._format_alarm_record(record)
        self.assertEqual(dto.status, AlertStatus.FIRING)

    def test_source_is_skywalking(self):
        record = self._make_record()
        dto = self.provider._format_alarm_record(record)
        self.assertIn("skywalking", dto.source)

    def test_default_severity_high(self):
        record = self._make_record(message="Service latency exceeded threshold")
        dto = self.provider._format_alarm_record(record)
        self.assertEqual(dto.severity, AlertSeverity.HIGH)

    def test_severity_from_message_warning(self):
        record = self._make_record(message="warning: cpu usage is elevated")
        dto = self.provider._format_alarm_record(record)
        self.assertEqual(dto.severity, AlertSeverity.WARNING)

    def test_severity_from_message_critical(self):
        record = self._make_record(message="critical: database connection pool exhausted")
        dto = self.provider._format_alarm_record(record)
        self.assertEqual(dto.severity, AlertSeverity.CRITICAL)

    def test_timestamp_parsed(self):
        record = self._make_record(startTime=1743200000000)
        dto = self.provider._format_alarm_record(record)
        self.assertIsNotNone(dto.lastReceived)
        self.assertIn("2025-03-28", dto.lastReceived)

    def test_missing_start_time(self):
        record = self._make_record()
        del record["startTime"]
        dto = self.provider._format_alarm_record(record)
        self.assertIsNone(dto.lastReceived)

    def test_labels_contain_scope(self):
        record = self._make_record(scope="ServiceInstance")
        dto = self.provider._format_alarm_record(record)
        self.assertEqual(dto.labels["scope"], "ServiceInstance")

    def test_labels_contain_scope_id(self):
        record = self._make_record(scopeId="some-scope-id")
        dto = self.provider._format_alarm_record(record)
        self.assertEqual(dto.labels["scopeId"], "some-scope-id")

    def test_description_from_message(self):
        record = self._make_record(message="My custom alarm message")
        dto = self.provider._format_alarm_record(record)
        self.assertEqual(dto.description, "My custom alarm message")


# ---------------------------------------------------------------------------
# Provider config and auth tests
# ---------------------------------------------------------------------------


class TestSkywalkingProviderConfig(unittest.TestCase):
    def test_validate_config_sets_auth(self):
        provider = _make_provider()
        self.assertEqual(
            str(provider.authentication_config.oap_url),
            "http://skywalking-oap:12800/",
        )

    def test_token_is_optional(self):
        provider = _make_provider()
        self.assertIsNone(provider.authentication_config.token)

    def test_graphql_url_constructed_correctly(self):
        provider = _make_provider()
        self.assertEqual(provider._graphql_url(), "http://skywalking-oap:12800/graphql")

    def test_headers_without_token(self):
        provider = _make_provider()
        headers = provider._get_headers()
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertNotIn("Authorization", headers)

    def test_headers_with_token(self):
        mock_context = MagicMock(spec=ContextManager)
        mock_context.tenant_id = "test"
        mock_context.workflow_id = None
        config = ProviderConfig(
            authentication={"oap_url": "http://skywalking-oap:12800", "token": "my-secret"},
            name="sw",
            description="Test",
        )
        provider = SkywalkingProvider(
            context_manager=mock_context, provider_id="sw-2", config=config
        )
        headers = provider._get_headers()
        self.assertEqual(headers["Authorization"], "Bearer my-secret")

    def test_validate_scopes_returns_connectivity_key(self):
        provider = _make_provider()
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            result = provider.validate_scopes()
        self.assertIn("connectivity", result)
        self.assertTrue(result["connectivity"])

    def test_validate_scopes_non_200_returns_error_string(self):
        provider = _make_provider()
        with patch("requests.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=403, text="Forbidden")
            result = provider.validate_scopes()
        self.assertIn("403", result["connectivity"])

    def test_validate_scopes_exception_returns_error_string(self):
        provider = _make_provider()
        with patch("requests.post", side_effect=ConnectionError("refused")):
            result = provider.validate_scopes()
        self.assertIn("refused", result["connectivity"])


# ---------------------------------------------------------------------------
# Pull / _get_alerts tests
# ---------------------------------------------------------------------------


class TestSkywalkingGetAlerts(unittest.TestCase):
    def setUp(self):
        self.provider = _make_provider()

    def test_get_alerts_returns_list_of_dtos(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {
                "getAlarm": {
                    "items": [
                        {
                            "id": "1",
                            "message": "Service latency spike",
                            "startTime": 1743200000000,
                            "scope": "Service",
                            "scopeId": "svc1",
                            "name": "api-gateway",
                        }
                    ],
                    "total": 1,
                }
            }
        }
        with patch("requests.post", return_value=mock_response):
            alerts = self.provider._get_alerts()
        self.assertIsInstance(alerts, list)
        self.assertEqual(len(alerts), 1)
        self.assertIsInstance(alerts[0], AlertDto)

    def test_get_alerts_empty_list_on_no_alarms(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"getAlarm": {"items": [], "total": 0}}
        }
        with patch("requests.post", return_value=mock_response):
            alerts = self.provider._get_alerts()
        self.assertEqual(alerts, [])

    def test_get_alerts_returns_empty_list_on_error(self):
        with patch("requests.post", side_effect=ConnectionError("refused")):
            alerts = self.provider._get_alerts()
        self.assertEqual(alerts, [])

    def test_get_alerts_multiple_records(self):
        items = [
            {
                "id": str(i),
                "message": f"Alarm {i}",
                "startTime": 1743200000000 + i * 1000,
                "scope": "Service",
                "scopeId": f"svc{i}",
                "name": f"service-{i}",
            }
            for i in range(5)
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"getAlarm": {"items": items, "total": 5}}
        }
        with patch("requests.post", return_value=mock_response):
            alerts = self.provider._get_alerts()
        self.assertEqual(len(alerts), 5)

    def test_get_alerts_null_items_handled(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"getAlarm": {"items": None, "total": 0}}
        }
        with patch("requests.post", return_value=mock_response):
            alerts = self.provider._get_alerts()
        self.assertEqual(alerts, [])


# ---------------------------------------------------------------------------
# Alerts mock sanity tests
# ---------------------------------------------------------------------------


class TestSkywalkingAlertsMock(unittest.TestCase):
    def test_alerts_mock_parseable(self):
        from keep.providers.skywalking_provider.alerts_mock import ALERTS

        for name, alert_def in ALERTS.items():
            payload = alert_def["payload"]
            result = SkywalkingProvider._format_alert(payload)
            # Each mock should yield at least one AlertDto
            if isinstance(result, list):
                self.assertGreater(len(result), 0, f"Empty result for mock '{name}'")
                for dto in result:
                    self.assertIsInstance(dto, AlertDto, f"Not an AlertDto in mock '{name}'")
            else:
                self.assertIsInstance(result, AlertDto, f"Not an AlertDto for mock '{name}'")


if __name__ == "__main__":
    unittest.main()
