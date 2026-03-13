import time
import unittest
from unittest.mock import MagicMock, patch

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.lark_provider.lark_provider import LarkProvider


class TestLarkFormatAlert(unittest.TestCase):
    """Tests for LarkProvider._format_alert static method."""

    def _make_event(self, priority=None, status="open", ticket_id="T001", summary="Test ticket"):
        ticket = {
            "ticket_id": ticket_id,
            "summary": summary,
            "description": "desc",
            "status": {"name": status},
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T01:00:00Z",
            "helpdesk_id": "HD1",
        }
        if priority is not None:
            ticket["priority"] = priority
        return {
            "header": {"event_type": "helpdesk.ticket.created_v1"},
            "event": {"ticket": ticket},
        }

    def test_priority_urgent(self):
        alert = LarkProvider._format_alert(self._make_event(priority=1))
        self.assertEqual(alert.severity, AlertSeverity.CRITICAL)

    def test_priority_high(self):
        alert = LarkProvider._format_alert(self._make_event(priority=2))
        self.assertEqual(alert.severity, AlertSeverity.HIGH)

    def test_priority_medium(self):
        alert = LarkProvider._format_alert(self._make_event(priority=3))
        self.assertEqual(alert.severity, AlertSeverity.WARNING)

    def test_priority_low(self):
        alert = LarkProvider._format_alert(self._make_event(priority=4))
        self.assertEqual(alert.severity, AlertSeverity.LOW)

    def test_priority_string_high(self):
        alert = LarkProvider._format_alert(self._make_event(priority="high"))
        self.assertEqual(alert.severity, AlertSeverity.HIGH)

    def test_no_priority_defaults_info(self):
        alert = LarkProvider._format_alert(self._make_event())
        self.assertEqual(alert.severity, AlertSeverity.INFO)

    def test_status_resolved(self):
        alert = LarkProvider._format_alert(self._make_event(status="resolved"))
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_status_closed(self):
        alert = LarkProvider._format_alert(self._make_event(status="closed"))
        self.assertEqual(alert.status, AlertStatus.RESOLVED)

    def test_status_open(self):
        alert = LarkProvider._format_alert(self._make_event(status="open"))
        self.assertEqual(alert.status, AlertStatus.FIRING)

    def test_alert_id(self):
        alert = LarkProvider._format_alert(self._make_event(ticket_id="T999"))
        self.assertEqual(alert.id, "lark-T999")

    def test_source(self):
        alert = LarkProvider._format_alert(self._make_event())
        self.assertEqual(alert.source, ["lark"])


class TestLarkTokenCache(unittest.TestCase):
    """Tests for token TTL refresh logic."""

    @patch("keep.providers.lark_provider.lark_provider.requests.post")
    def test_token_refreshed_after_ttl(self, mock_post):
        mock_post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"code": 0, "tenant_access_token": "tok1"}),
        )

        provider = LarkProvider.__new__(LarkProvider)
        provider._tenant_access_token = None
        provider._token_obtained_at = 0
        provider.authentication_config = MagicMock(app_id="id", app_secret="secret")

        # First call — fetches token
        token1 = provider._get_tenant_access_token()
        self.assertEqual(token1, "tok1")
        self.assertEqual(mock_post.call_count, 1)

        # Second call within TTL — cached
        token2 = provider._get_tenant_access_token()
        self.assertEqual(token2, "tok1")
        self.assertEqual(mock_post.call_count, 1)

        # Simulate TTL expiry
        provider._token_obtained_at = time.time() - (LarkProvider._TOKEN_TTL_SECONDS + 1)
        mock_post.return_value.json.return_value = {"code": 0, "tenant_access_token": "tok2"}

        token3 = provider._get_tenant_access_token()
        self.assertEqual(token3, "tok2")
        self.assertEqual(mock_post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
