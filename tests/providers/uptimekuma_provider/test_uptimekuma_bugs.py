"""
Tests for UptimeKuma provider critical bug fixes (issue #5655).

Bug 1: heartbeats.append() was outside for-loop → only last monitor reported
Bug 2: _format_datetime TypeError → string + int or datetime + string
Bug 3: _format_alert KeyError → non-existent fields accessed without .get()
Bug 4: Connection not closed on exception → missing try/finally
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from keep.providers.uptimekuma_provider.uptimekuma_provider import UptimekumaProvider


class TestFormatDatetime:
    """Bug 2: _format_datetime TypeError"""

    def test_string_dt_string_offset(self):
        """Webhook payload: both dt and offset are strings."""
        result = UptimekumaProvider._format_datetime("2022-08-26 01:02:24", "+00:00")
        assert result == "2022-08-26 01:02:24+00:00"

    def test_string_dt_numeric_offset_zero(self):
        """Pull API: dt is string, offset is integer minutes (UTC=0)."""
        result = UptimekumaProvider._format_datetime("2022-08-26 01:02:24", 0)
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_string_dt_numeric_offset_positive(self):
        """Pull API: numeric offset +330 (UTC+5:30)."""
        result = UptimekumaProvider._format_datetime("2022-08-26 01:02:24", 330)
        assert isinstance(result, datetime)
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_string_dt_numeric_offset_negative(self):
        """Pull API: numeric offset -300 (UTC-5)."""
        result = UptimekumaProvider._format_datetime("2022-08-26 01:02:24", -300)
        assert isinstance(result, datetime)
        assert result.utcoffset() == timedelta(hours=-5)

    def test_datetime_object_numeric_offset(self):
        """Pull API returns actual datetime object."""
        dt = datetime(2022, 8, 26, 1, 2, 24)
        result = UptimekumaProvider._format_datetime(dt, 60)
        assert isinstance(result, datetime)
        assert result.utcoffset() == timedelta(hours=1)

    def test_datetime_object_no_offset(self):
        """Datetime object with non-numeric offset falls back gracefully."""
        dt = datetime(2022, 8, 26, 1, 2, 24)
        result = UptimekumaProvider._format_datetime(dt, "invalid")
        assert result == dt

    def test_empty_string_returns_string(self):
        """Graceful fallback for empty/bad input."""
        result = UptimekumaProvider._format_datetime("", 0)
        assert isinstance(result, str)


class TestFormatAlert:
    """Bug 3: _format_alert KeyError on missing fields"""

    def test_full_webhook_payload(self):
        """Normal webhook payload with all fields present."""
        event = {
            "monitor": {"id": 1, "name": "My Site", "url": "https://example.com"},
            "heartbeat": {
                "status": 1,
                "localDateTime": "2022-08-26 01:02:24",
                "timezoneOffset": "+00:00",
                "msg": "Service online",
            },
            "msg": "Service online",
        }
        alert = UptimekumaProvider._format_alert(event)
        # AlertDto coerces id to str
        assert alert.id == "1"
        assert alert.name == "My Site"
        assert alert.monitor_url == "https://example.com"
        assert alert.status == "resolved"  # status=1 maps to resolved

    def test_missing_monitor_url(self):
        """Port monitors don't have a URL field."""
        event = {
            "monitor": {"id": 2, "name": "Port Monitor"},  # no "url"
            "heartbeat": {
                "status": 0,
                "localDateTime": "2022-08-26 01:02:24",
                "timezoneOffset": "+00:00",
                "msg": "Port closed",
            },
            "msg": "Port closed",
        }
        alert = UptimekumaProvider._format_alert(event)
        assert alert.id == "2"
        assert alert.monitor_url is None
        assert alert.status == "firing"

    def test_missing_msg_fallback_to_heartbeat_msg(self):
        """If top-level msg is missing, fall back to heartbeat.msg."""
        event = {
            "monitor": {"id": 3, "name": "Test"},
            "heartbeat": {
                "status": 1,
                "localDateTime": "2022-08-26 01:02:24",
                "timezoneOffset": "+00:00",
                "msg": "All good",
            },
            # no top-level "msg"
        }
        alert = UptimekumaProvider._format_alert(event)
        assert alert.description == "All good"

    def test_completely_empty_event(self):
        """Should not raise KeyError even with empty event dict."""
        alert = UptimekumaProvider._format_alert({})
        assert alert.source == ["uptimekuma"]


class TestGetHeartbeats:
    """Bug 1: append outside loop + Bug 4: connection not closed"""

    def _make_provider(self):
        from keep.contextmanager.contextmanager import ContextManager
        from keep.providers.models.provider_config import ProviderConfig

        context_manager = ContextManager(tenant_id="test", workflow_id="test")
        config = ProviderConfig(
            authentication={
                "host_url": "http://localhost:3001",
                "username": "test",
                "password": "test",
            },
            name="test-uptimekuma",
        )
        return UptimekumaProvider(context_manager, "uptimekuma", config)

    def test_all_monitors_reported(self):
        """Bug 1: all monitors in response must be returned, not just the last."""
        provider = self._make_provider()

        mock_api = MagicMock()
        mock_api.get_heartbeats.return_value = {
            "monitor_1": [{"id": 10, "monitor_id": 1, "status": 1, "msg": "OK", "localDateTime": "2022-01-01 00:00:00", "timezoneOffset": 0, "ping": 5}],
            "monitor_2": [{"id": 20, "monitor_id": 2, "status": 0, "msg": "Down", "localDateTime": "2022-01-01 00:00:00", "timezoneOffset": 0, "ping": None}],
            "monitor_3": [{"id": 30, "monitor_id": 3, "status": 1, "msg": "OK", "localDateTime": "2022-01-01 00:00:00", "timezoneOffset": 0, "ping": 10}],
        }
        mock_api.get_monitor.side_effect = lambda mid: {"name": f"Monitor {mid}"}

        with patch.object(provider, "_get_api", return_value=mock_api):
            alerts = provider._get_heartbeats()

        assert len(alerts) == 3, f"Expected 3 alerts, got {len(alerts)}"
        # AlertDto coerces id to str
        alert_ids = {a.id for a in alerts}
        assert alert_ids == {"10", "20", "30"}

    def test_connection_closed_on_success(self):
        """Bug 4: disconnect() must be called even on success."""
        provider = self._make_provider()

        mock_api = MagicMock()
        mock_api.get_heartbeats.return_value = {
            "monitor_1": [{"id": 1, "monitor_id": 1, "status": 1, "msg": "OK", "localDateTime": "2022-01-01 00:00:00", "timezoneOffset": 0, "ping": 5}],
        }
        mock_api.get_monitor.return_value = {"name": "Monitor 1"}

        with patch.object(provider, "_get_api", return_value=mock_api):
            provider._get_heartbeats()

        mock_api.disconnect.assert_called_once()

    def test_connection_closed_on_exception(self):
        """Bug 4: disconnect() must be called even when an exception occurs."""
        provider = self._make_provider()

        mock_api = MagicMock()
        mock_api.get_heartbeats.side_effect = RuntimeError("socket error")

        with patch.object(provider, "_get_api", return_value=mock_api):
            with pytest.raises(Exception, match="socket error"):
                provider._get_heartbeats()

        mock_api.disconnect.assert_called_once()

    def test_empty_response_returns_empty_list(self):
        """Empty heartbeat response returns empty list."""
        provider = self._make_provider()

        mock_api = MagicMock()
        mock_api.get_heartbeats.return_value = {}

        with patch.object(provider, "_get_api", return_value=mock_api):
            alerts = provider._get_heartbeats()

        assert alerts == []
        mock_api.disconnect.assert_called_once()
