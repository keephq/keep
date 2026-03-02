"""Tests for GCP Pub/Sub provider."""

import base64
import json

import pytest

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.gcp_pubsub_provider.gcp_pubsub_provider import (
    GcpPubsubProvider,
)


class TestGcpPubsubFormatAlert:
    """Test _format_alert with different GKE notification types."""

    @staticmethod
    def _make_event(notification_type, title, description, cluster_name="test-cluster", message_id="msg-001"):
        return {
            "type_url": notification_type,
            "cluster_name": cluster_name,
            "title": title,
            "description": description,
            "pubsub_message_id": message_id,
            "pubsub_publish_time": "2024-01-15T10:30:00.000Z",
            "pubsub_attributes": {
                "notification_type": notification_type,
                "cluster_name": cluster_name,
            },
        }

    def test_security_bulletin(self):
        event = self._make_event(
            "SECURITY_BULLETIN",
            "GKE Security Bulletin: CVE-2024-1234",
            "A vulnerability was found in the Linux kernel.",
        )
        alert = GcpPubsubProvider._format_alert(event)
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.name == "GKE Security Bulletin: CVE-2024-1234"
        assert alert.status == AlertStatus.FIRING
        assert "gcp_pubsub" in alert.source

    def test_upgrade_available(self):
        event = self._make_event(
            "UPGRADE_AVAILABLE",
            "GKE Upgrade Available: 1.28.2",
            "A new version is available.",
        )
        alert = GcpPubsubProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO

    def test_upgrade_forced(self):
        event = self._make_event(
            "UPGRADE_FORCED",
            "GKE Forced Upgrade",
            "Your cluster will be automatically upgraded.",
        )
        alert = GcpPubsubProvider._format_alert(event)
        assert alert.severity == AlertSeverity.WARNING

    def test_end_of_support(self):
        event = self._make_event(
            "END_OF_SUPPORT",
            "GKE End of Support",
            "Version 1.24 is no longer supported.",
        )
        alert = GcpPubsubProvider._format_alert(event)
        assert alert.severity == AlertSeverity.HIGH

    def test_unknown_type_defaults_to_info(self):
        event = self._make_event(
            "SOME_NEW_TYPE",
            "Unknown notification",
            "Something happened.",
        )
        alert = GcpPubsubProvider._format_alert(event)
        assert alert.severity == AlertSeverity.INFO

    def test_parse_pubsub_message(self):
        payload = {"title": "Test", "description": "Test message"}
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        message = {
            "data": encoded,
            "attributes": {"notification_type": "SECURITY_BULLETIN"},
            "messageId": "123",
            "publishTime": "2024-01-15T10:30:00.000Z",
        }
        result = GcpPubsubProvider._parse_pubsub_message(message)
        assert result["title"] == "Test"
        assert result["pubsub_message_id"] == "123"
        assert result["pubsub_attributes"]["notification_type"] == "SECURITY_BULLETIN"
