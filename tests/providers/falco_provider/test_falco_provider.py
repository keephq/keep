"""
Comprehensive unit tests for the Falco provider.

Test coverage:
  1.  Auth config — optional fields, SSL flag, token presence
  2.  Severity mapping — all 8 Falco priorities (case-insensitive)
  3.  Status heuristic — rule-name keywords → RESOLVED vs FIRING
  4.  Timestamp parsing — ISO-8601, nanoseconds, missing
  5.  _format_alert — single event, all standard output_fields
  6.  _format_alert — batch envelopes (events / alerts keys)
  7.  _format_alert — Falcosidekick envelope shape
  8.  _format_alert — missing / partial / empty fields
  9.  _format_alert — labels mapping (container, k8s, process, user)
  10. _format_alert — tags handling
  11. _format_alert — returns AlertDto type
  12. _format_alert — id uniqueness
  13. _format_alert — source always contains "falco"
  14. validate_scopes — webhook-only (no sidekick_url) returns True
  15. validate_scopes — pull mode success
  16. validate_scopes — pull mode failure
  17. _get_alerts — webhook-only returns empty list
  18. _get_alerts — sidekick returns list of AlertDtos
  19. _get_alerts — sidekick API error returns empty list
  20. _get_alerts — sidekick response with alerts key
  21. _sidekick_request — builds correct URL
  22. _sidekick_request — sends auth header when token present
  23. _sidekick_request — raises on HTTP error
  24. _sidekick_request — raises ValueError when sidekick_url missing
  25. dispose — closes session
  26. _copy_field helper
"""

import datetime
import unittest
from unittest.mock import MagicMock, patch

import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.falco_provider.falco_provider import (
    FALCO_SEVERITY_MAP,
    FalcoProvider,
    FalcoProviderAuthConfig,
    _copy_field,
    _parse_timestamp,
    _severity_from_priority,
    _status_from_rule,
)
from keep.providers.models.provider_config import ProviderConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(auth_overrides: dict | None = None) -> FalcoProvider:
    base: dict = {}
    if auth_overrides:
        base.update(auth_overrides)
    ctx = MagicMock(spec=ContextManager)
    config = ProviderConfig(authentication=base)
    provider = FalcoProvider(context_manager=ctx, provider_id="test-falco", config=config)
    provider.validate_config()
    return provider


def _basic_event(**kwargs) -> dict:
    base = {
        "rule": "Write below root",
        "priority": "Warning",
        "output": "15:00:00.000000000: Warning File opened for writing by root",
        "output_fields": {
            "user.name": "root",
            "proc.name": "bash",
            "fd.name": "/etc/passwd",
            "evt.type": "open",
        },
        "time": "2026-03-29T15:00:00.000000000Z",
        "tags": ["filesystem", "mitre_persistence"],
    }
    base.update(kwargs)
    return base


# ===========================================================================
# 1. Auth config
# ===========================================================================


class TestFalcoProviderAuthConfig(unittest.TestCase):
    def test_no_credentials_accepted(self):
        provider = _make_provider()
        cfg = provider.authentication_config
        self.assertEqual(cfg.sidekick_url, "")
        self.assertEqual(cfg.api_token, "")

    def test_sidekick_url_stored(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        self.assertEqual(
            provider.authentication_config.sidekick_url, "http://falcosidekick:2801"
        )

    def test_api_token_stored(self):
        provider = _make_provider({"api_token": "secret-token"})
        self.assertEqual(provider.authentication_config.api_token, "secret-token")

    def test_verify_ssl_default_true(self):
        provider = _make_provider()
        self.assertTrue(provider.authentication_config.verify_ssl)

    def test_verify_ssl_false_accepted(self):
        provider = _make_provider({"verify_ssl": False})
        self.assertFalse(provider.authentication_config.verify_ssl)

    def test_empty_config_no_raise(self):
        try:
            _make_provider()
        except Exception as exc:
            self.fail(f"Empty config raised: {exc}")


# ===========================================================================
# 2. Severity mapping
# ===========================================================================


class TestSeverityMapping(unittest.TestCase):
    def test_emergency_is_critical(self):
        self.assertEqual(_severity_from_priority("Emergency"), AlertSeverity.CRITICAL)

    def test_alert_is_critical(self):
        self.assertEqual(_severity_from_priority("Alert"), AlertSeverity.CRITICAL)

    def test_critical_is_critical(self):
        self.assertEqual(_severity_from_priority("Critical"), AlertSeverity.CRITICAL)

    def test_error_is_critical(self):
        self.assertEqual(_severity_from_priority("Error"), AlertSeverity.CRITICAL)

    def test_warning_is_warning(self):
        self.assertEqual(_severity_from_priority("Warning"), AlertSeverity.WARNING)

    def test_notice_is_info(self):
        self.assertEqual(_severity_from_priority("Notice"), AlertSeverity.INFO)

    def test_informational_is_info(self):
        self.assertEqual(_severity_from_priority("Informational"), AlertSeverity.INFO)

    def test_debug_is_low(self):
        self.assertEqual(_severity_from_priority("Debug"), AlertSeverity.LOW)

    def test_case_insensitive_warning(self):
        self.assertEqual(_severity_from_priority("WARNING"), AlertSeverity.WARNING)

    def test_case_insensitive_critical(self):
        self.assertEqual(_severity_from_priority("CRITICAL"), AlertSeverity.CRITICAL)

    def test_case_insensitive_debug(self):
        self.assertEqual(_severity_from_priority("DEBUG"), AlertSeverity.LOW)

    def test_unknown_priority_defaults_to_info(self):
        self.assertEqual(_severity_from_priority("fancy-custom"), AlertSeverity.INFO)

    def test_empty_string_defaults_to_info(self):
        self.assertEqual(_severity_from_priority(""), AlertSeverity.INFO)

    def test_severity_map_has_all_8_priorities(self):
        self.assertEqual(len(FALCO_SEVERITY_MAP), 8)


# ===========================================================================
# 3. Status heuristic
# ===========================================================================


class TestStatusHeuristic(unittest.TestCase):
    def test_normal_rule_is_firing(self):
        self.assertEqual(_status_from_rule("Write below root"), AlertStatus.FIRING)

    def test_resolved_keyword(self):
        self.assertEqual(_status_from_rule("Alert Resolved"), AlertStatus.RESOLVED)

    def test_recovered_keyword(self):
        self.assertEqual(_status_from_rule("Process Recovered"), AlertStatus.RESOLVED)

    def test_terminated_keyword(self):
        self.assertEqual(_status_from_rule("Container Terminated"), AlertStatus.RESOLVED)

    def test_stopped_keyword(self):
        self.assertEqual(_status_from_rule("Service Stopped"), AlertStatus.RESOLVED)

    def test_closed_keyword(self):
        self.assertEqual(_status_from_rule("Connection Closed"), AlertStatus.RESOLVED)

    def test_case_insensitive_keyword(self):
        self.assertEqual(_status_from_rule("PROCESS TERMINATED"), AlertStatus.RESOLVED)

    def test_empty_rule_is_firing(self):
        self.assertEqual(_status_from_rule(""), AlertStatus.FIRING)

    def test_partial_match_firing(self):
        # "closedown" should NOT match "closed" — keyword not present
        self.assertEqual(_status_from_rule("closedown event"), AlertStatus.FIRING)


# ===========================================================================
# 4. Timestamp parsing
# ===========================================================================


class TestTimestampParsing(unittest.TestCase):
    def test_standard_iso_parses(self):
        dt = _parse_timestamp("2026-03-29T10:00:00Z")
        self.assertIsInstance(dt, datetime.datetime)

    def test_nanosecond_precision_parsed(self):
        dt = _parse_timestamp("2026-03-29T10:00:00.123456789Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.second, 0)

    def test_microsecond_precision_parsed(self):
        dt = _parse_timestamp("2026-03-29T10:00:00.123456Z")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.microsecond, 123456)

    def test_none_returns_none(self):
        self.assertIsNone(_parse_timestamp(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_timestamp(""))

    def test_invalid_string_returns_none(self):
        self.assertIsNone(_parse_timestamp("not-a-date"))

    def test_timezone_is_utc(self):
        dt = _parse_timestamp("2026-03-29T10:00:00Z")
        self.assertEqual(dt.tzinfo, datetime.timezone.utc)


# ===========================================================================
# 5. _format_alert — single event
# ===========================================================================


class TestFormatAlertSingle(unittest.TestCase):
    def test_returns_alert_dto(self):
        alert = FalcoProvider._format_alert(_basic_event())
        self.assertIsInstance(alert, AlertDto)

    def test_name_is_rule(self):
        alert = FalcoProvider._format_alert(_basic_event(rule="Shell in container"))
        self.assertEqual(alert.name, "Shell in container")

    def test_severity_warning(self):
        alert = FalcoProvider._format_alert(_basic_event(priority="Warning"))
        self.assertEqual(alert.severity, AlertSeverity.WARNING)

    def test_severity_critical(self):
        alert = FalcoProvider._format_alert(_basic_event(priority="Critical"))
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_severity_debug_is_low(self):
        alert = FalcoProvider._format_alert(_basic_event(priority="Debug"))
        self.assertEqual(alert.severity, AlertSeverity.LOW)

    def test_status_firing_for_generic_rule(self):
        alert = FalcoProvider._format_alert(_basic_event())
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_description_is_output(self):
        event = _basic_event(output="My custom output message")
        alert = FalcoProvider._format_alert(event)
        self.assertEqual(alert.description, "My custom output message")

    def test_source_contains_falco(self):
        alert = FalcoProvider._format_alert(_basic_event())
        self.assertIn("falco", alert.source)

    def test_last_received_is_datetime(self):
        alert = FalcoProvider._format_alert(_basic_event())
        self.assertIsInstance(alert.lastReceived, datetime.datetime)

    def test_timestamp_parsed_from_event_time(self):
        event = _basic_event(time="2026-01-15T08:30:00.000000000Z")
        alert = FalcoProvider._format_alert(event)
        self.assertEqual(alert.lastReceived.month, 1)
        self.assertEqual(alert.lastReceived.day, 15)

    def test_id_is_string(self):
        alert = FalcoProvider._format_alert(_basic_event())
        self.assertIsInstance(alert.id, str)
        self.assertTrue(len(alert.id) > 0)

    def test_fallback_name_when_rule_missing(self):
        event = _basic_event()
        del event["rule"]
        alert = FalcoProvider._format_alert(event)
        self.assertTrue(len(alert.name) > 0)

    def test_priority_key_alternative_casing(self):
        event = _basic_event()
        event["Priority"] = "Critical"
        del event["priority"]
        alert = FalcoProvider._format_alert(event)
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)


# ===========================================================================
# 6. _format_alert — batch envelopes
# ===========================================================================


class TestFormatAlertBatch(unittest.TestCase):
    def _events_envelope(self) -> dict:
        return {
            "events": [
                _basic_event(rule="Rule A", priority="Critical"),
                _basic_event(rule="Rule B", priority="Debug"),
            ]
        }

    def _alerts_envelope(self) -> dict:
        return {
            "alerts": [
                _basic_event(rule="Rule C", priority="Warning"),
            ]
        }

    def test_events_key_returns_list(self):
        result = FalcoProvider._format_alert(self._events_envelope())
        self.assertIsInstance(result, list)

    def test_events_key_count(self):
        result = FalcoProvider._format_alert(self._events_envelope())
        self.assertEqual(len(result), 2)

    def test_events_key_items_are_alert_dtos(self):
        result = FalcoProvider._format_alert(self._events_envelope())
        for item in result:
            self.assertIsInstance(item, AlertDto)

    def test_alerts_key_returns_list(self):
        result = FalcoProvider._format_alert(self._alerts_envelope())
        self.assertIsInstance(result, list)

    def test_alerts_key_count(self):
        result = FalcoProvider._format_alert(self._alerts_envelope())
        self.assertEqual(len(result), 1)

    def test_batch_severities_preserved(self):
        result = FalcoProvider._format_alert(self._events_envelope())
        self.assertEqual(result[0].severity, AlertSeverity.CRITICAL)
        self.assertEqual(result[1].severity, AlertSeverity.LOW)

    def test_empty_batch_falls_back_to_single(self):
        payload = {"events": [], "rule": "Fallback Rule", "priority": "Warning"}
        result = FalcoProvider._format_alert(payload)
        # Falls through to single-event path
        self.assertIsInstance(result, AlertDto)


# ===========================================================================
# 7. _format_alert — Falcosidekick envelope shape
# ===========================================================================


class TestFormatAlertSidekickShape(unittest.TestCase):
    def _sidekick_event(self) -> dict:
        return {
            "Rule": "Unexpected network connection",
            "Priority": "Error",
            "Output": "Container opened unexpected network connection",
            "outputFields": {
                "container.id": "abc123",
                "k8s.pod.name": "my-api-pod",
                "k8s.ns.name": "production",
                "user.name": "www-data",
            },
            "Time": "2026-03-29T12:00:00.000000000Z",
            "hostname": "node-1",
        }

    def test_sidekick_shape_returns_alert_dto(self):
        alert = FalcoProvider._format_alert(self._sidekick_event())
        self.assertIsInstance(alert, AlertDto)

    def test_sidekick_rule_key_capitalised(self):
        alert = FalcoProvider._format_alert(self._sidekick_event())
        self.assertEqual(alert.name, "Unexpected network connection")

    def test_sidekick_priority_capitalised(self):
        alert = FalcoProvider._format_alert(self._sidekick_event())
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_sidekick_output_fields_alias(self):
        alert = FalcoProvider._format_alert(self._sidekick_event())
        self.assertEqual(alert.labels.get("container_id"), "abc123")

    def test_sidekick_hostname_in_labels(self):
        alert = FalcoProvider._format_alert(self._sidekick_event())
        self.assertEqual(alert.labels.get("hostname"), "node-1")


# ===========================================================================
# 8. _format_alert — missing / partial / empty fields
# ===========================================================================


class TestFormatAlertEdgeCases(unittest.TestCase):
    def test_empty_dict_returns_alert_dto(self):
        alert = FalcoProvider._format_alert({})
        self.assertIsInstance(alert, AlertDto)

    def test_no_output_fields_no_labels(self):
        alert = FalcoProvider._format_alert({"rule": "X", "priority": "Warning"})
        # Labels may still have tags or hostname, but container_id should be absent
        self.assertNotIn("container_id", alert.labels)

    def test_none_output_fields_no_crash(self):
        event = _basic_event()
        event["output_fields"] = None
        alert = FalcoProvider._format_alert(event)
        self.assertIsInstance(alert, AlertDto)

    def test_missing_time_uses_now(self):
        event = _basic_event()
        del event["time"]
        alert = FalcoProvider._format_alert(event)
        self.assertIsNotNone(alert.lastReceived)

    def test_empty_tags_no_tags_label(self):
        event = _basic_event(tags=[])
        alert = FalcoProvider._format_alert(event)
        self.assertNotIn("tags", alert.labels)

    def test_output_none_falls_back_to_rule(self):
        event = _basic_event()
        event["output"] = None
        alert = FalcoProvider._format_alert(event)
        # description should be the rule or empty — not crash
        self.assertIsInstance(alert.description, (str, type(None)))


# ===========================================================================
# 9. _format_alert — labels mapping
# ===========================================================================


class TestFormatAlertLabels(unittest.TestCase):
    def _rich_event(self) -> dict:
        return _basic_event(
            output_fields={
                "container.id": "c0ffee",
                "container.name": "api",
                "container.image.repository": "myrepo/api",
                "k8s.pod.name": "api-pod-123",
                "k8s.ns.name": "default",
                "k8s.deployment.name": "api-deploy",
                "proc.name": "bash",
                "proc.cmdline": "bash -c whoami",
                "user.name": "root",
                "fd.name": "/etc/shadow",
                "evt.type": "open",
            }
        )

    def test_container_id_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["container_id"], "c0ffee")

    def test_container_name_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["container_name"], "api")

    def test_image_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["image"], "myrepo/api")

    def test_pod_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["pod"], "api-pod-123")

    def test_namespace_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["namespace"], "default")

    def test_deployment_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["deployment"], "api-deploy")

    def test_process_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["process"], "bash")

    def test_cmdline_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["cmdline"], "bash -c whoami")

    def test_user_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["user"], "root")

    def test_fd_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["fd"], "/etc/shadow")

    def test_syscall_in_labels(self):
        alert = FalcoProvider._format_alert(self._rich_event())
        self.assertEqual(alert.labels["syscall"], "open")


# ===========================================================================
# 10. _format_alert — tags handling
# ===========================================================================


class TestFormatAlertTags(unittest.TestCase):
    def test_tags_joined_in_labels(self):
        event = _basic_event(tags=["tag1", "tag2", "tag3"])
        alert = FalcoProvider._format_alert(event)
        self.assertIn("tag1", alert.labels.get("tags", ""))
        self.assertIn("tag2", alert.labels.get("tags", ""))

    def test_single_tag(self):
        event = _basic_event(tags=["mitre_persistence"])
        alert = FalcoProvider._format_alert(event)
        self.assertEqual(alert.labels["tags"], "mitre_persistence")

    def test_numeric_tag_converted_to_string(self):
        event = _basic_event(tags=[42])
        alert = FalcoProvider._format_alert(event)
        self.assertIn("42", alert.labels.get("tags", ""))


# ===========================================================================
# 11. _format_alert — id uniqueness
# ===========================================================================


class TestAlertIdUniqueness(unittest.TestCase):
    def test_two_alerts_have_different_ids(self):
        a1 = FalcoProvider._format_alert(_basic_event())
        a2 = FalcoProvider._format_alert(_basic_event())
        self.assertNotEqual(a1.id, a2.id)

    def test_id_is_valid_uuid(self):
        import uuid
        alert = FalcoProvider._format_alert(_basic_event())
        uuid.UUID(alert.id)  # must not raise


# ===========================================================================
# 12. validate_scopes
# ===========================================================================


class TestValidateScopes(unittest.TestCase):
    def test_webhook_only_returns_true(self):
        provider = _make_provider()
        result = provider.validate_scopes()
        self.assertTrue(result.get("falcosidekick:read"))

    def test_pull_mode_success(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        with patch.object(provider, "_sidekick_request", return_value={"status": "ok"}):
            result = provider.validate_scopes()
        self.assertTrue(result.get("falcosidekick:read"))

    def test_pull_mode_failure_returns_error_string(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        with patch.object(
            provider, "_sidekick_request", side_effect=ConnectionError("refused")
        ):
            result = provider.validate_scopes()
        self.assertIsInstance(result.get("falcosidekick:read"), str)
        self.assertIn("refused", result["falcosidekick:read"])


# ===========================================================================
# 13. _get_alerts
# ===========================================================================


class TestGetAlerts(unittest.TestCase):
    def test_webhook_only_returns_empty_list(self):
        provider = _make_provider()
        result = provider._get_alerts()
        self.assertEqual(result, [])

    def test_pull_mode_returns_list_of_alert_dtos(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        fake_response = [
            _basic_event(rule="Rule A"),
            _basic_event(rule="Rule B", priority="Critical"),
        ]
        with patch.object(provider, "_sidekick_request", return_value=fake_response):
            result = provider._get_alerts()
        self.assertEqual(len(result), 2)
        for item in result:
            self.assertIsInstance(item, AlertDto)

    def test_pull_mode_alerts_key_envelope(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        fake_response = {"alerts": [_basic_event(rule="Rule X")]}
        with patch.object(provider, "_sidekick_request", return_value=fake_response):
            result = provider._get_alerts()
        self.assertEqual(len(result), 1)

    def test_pull_mode_api_error_returns_empty_list(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        with patch.object(
            provider, "_sidekick_request", side_effect=requests.HTTPError("500")
        ):
            result = provider._get_alerts()
        self.assertEqual(result, [])

    def test_pull_mode_non_dict_items_skipped(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        fake_response = [
            _basic_event(rule="Valid"),
            "not-a-dict",
            123,
        ]
        with patch.object(provider, "_sidekick_request", return_value=fake_response):
            result = provider._get_alerts()
        # Only the valid dict should produce an alert
        self.assertEqual(len(result), 1)


# ===========================================================================
# 14. _sidekick_request
# ===========================================================================


class TestSidekickRequest(unittest.TestCase):
    def test_no_sidekick_url_raises_value_error(self):
        provider = _make_provider()
        with self.assertRaises(ValueError):
            provider._sidekick_request("ping")

    def test_url_constructed_correctly(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_resp.raise_for_status = MagicMock()
        session = provider._get_session()
        with patch.object(session, "get", return_value=mock_resp) as mock_get:
            provider._sidekick_request("ping")
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertEqual(call_url, "http://falcosidekick:2801/ping")

    def test_auth_header_sent_when_token_present(self):
        provider = _make_provider(
            {"sidekick_url": "http://falcosidekick:2801", "api_token": "my-secret"}
        )
        session = provider._get_session()
        self.assertIn("Authorization", session.headers)
        self.assertTrue(session.headers["Authorization"].startswith("Bearer "))

    def test_no_auth_header_when_no_token(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        session = provider._get_session()
        self.assertNotIn("Authorization", session.headers)

    def test_http_error_propagated(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        session = provider._get_session()
        with patch.object(session, "get", return_value=mock_resp):
            with self.assertRaises(requests.HTTPError):
                provider._sidekick_request("api/v1/alerts")

    def test_trailing_slash_stripped_from_base_url(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801/"})
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.raise_for_status = MagicMock()
        session = provider._get_session()
        with patch.object(session, "get", return_value=mock_resp) as mock_get:
            provider._sidekick_request("api/v1/alerts")
        call_url = mock_get.call_args[0][0]
        self.assertFalse(call_url.startswith("http://falcosidekick:2801//"))


# ===========================================================================
# 15. dispose
# ===========================================================================


class TestDispose(unittest.TestCase):
    def test_dispose_closes_session(self):
        provider = _make_provider({"sidekick_url": "http://falcosidekick:2801"})
        session = provider._get_session()
        with patch.object(session, "close") as mock_close:
            provider._session = session
            provider.dispose()
        mock_close.assert_called_once()
        self.assertIsNone(provider._session)

    def test_dispose_without_session_no_raise(self):
        provider = _make_provider()
        try:
            provider.dispose()
        except Exception as exc:
            self.fail(f"dispose() raised unexpectedly: {exc}")


# ===========================================================================
# 16. _copy_field helper
# ===========================================================================


class TestCopyField(unittest.TestCase):
    def test_copies_present_field(self):
        labels: dict = {}
        _copy_field(labels, {"container.id": "abc"}, "container.id", "container_id")
        self.assertEqual(labels["container_id"], "abc")

    def test_missing_field_not_added(self):
        labels: dict = {}
        _copy_field(labels, {}, "container.id", "container_id")
        self.assertNotIn("container_id", labels)

    def test_empty_string_not_added(self):
        labels: dict = {}
        _copy_field(labels, {"container.id": ""}, "container.id", "container_id")
        self.assertNotIn("container_id", labels)

    def test_whitespace_only_not_added(self):
        labels: dict = {}
        _copy_field(labels, {"container.id": "   "}, "container.id", "container_id")
        self.assertNotIn("container_id", labels)

    def test_numeric_value_converted_to_string(self):
        labels: dict = {}
        _copy_field(labels, {"proc.pid": 12345}, "proc.pid", "pid")
        self.assertEqual(labels["pid"], "12345")

    def test_none_value_not_added(self):
        labels: dict = {}
        _copy_field(labels, {"container.id": None}, "container.id", "container_id")
        self.assertNotIn("container_id", labels)


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main()
