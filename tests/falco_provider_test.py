"""
Tests for the Falco provider.
"""

import pytest
from datetime import datetime, timezone

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.providers.falco_provider.falco_provider import FalcoProvider


class TestFalcoProvider:
    """Test Falco provider."""

    def test_format_alert_container_shell(self):
        """Test formatting a container shell execution alert."""
        event = {
            "output": "12:34:56.789123789: Notice A shell was spawned in a container with an attached terminal (user=root user_loginuid=-1 k8s.ns=default k8s.pod=myapp-xyz container=abc123 shell=bash parent=docker-entrypoint cmdline=bash terminal=34816 exe_flags=EXE_WRITABLE container_id=abc123 container_image=myapp:latest)",
            "priority": "Notice",
            "rule": "Terminal shell in container",
            "time": "2024-01-15T12:34:56.789123789Z",
            "output_fields": {
                "container.id": "abc123",
                "container.image.repository": "myapp",
                "container.image.tag": "latest",
                "container.name": "myapp",
                "evt.time": 1705325696789123789,
                "k8s.ns.name": "default",
                "k8s.pod.name": "myapp-xyz",
                "proc.cmdline": "bash",
                "proc.name": "bash",
                "proc.pname": "docker-entrypoint",
                "user.loginuid": -1,
                "user.name": "root"
            },
            "hostname": "worker-node-1",
            "tags": ["container", "shell", "mitre_execution"]
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.name == "Terminal shell in container"
        assert alert.description == event["output"]
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == AlertStatus.FIRING
        assert alert.hostname == "worker-node-1"
        assert alert.source == ["falco"]
        assert "container" in alert.tags
        assert "shell" in alert.tags
        assert alert.labels["k8s_namespace"] == "default"
        assert alert.labels["k8s_pod"] == "myapp-xyz"
        assert alert.labels["container_name"] == "myapp"
        assert alert.labels["process_name"] == "bash"
        assert alert.labels["user_name"] == "root"

    def test_format_alert_privileged_container(self):
        """Test formatting a privileged container alert."""
        event = {
            "output": "10:20:30.123456789: Critical Privileged container started (user=admin user_loginuid=1000 k8s.ns=production k8s.pod=db-master-0 container=postgres image=postgres:15)",
            "priority": "Critical",
            "rule": "Launch Privileged Container",
            "time": "2024-01-15T10:20:30.123456789Z",
            "output_fields": {
                "container.id": "def456",
                "container.image.repository": "postgres",
                "container.image.tag": "15",
                "container.name": "postgres",
                "k8s.ns.name": "production",
                "k8s.pod.name": "db-master-0",
                "user.name": "admin"
            },
            "hostname": "worker-node-2",
            "tags": ["container", "cis", "mitre_privilege_escalation"]
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.name == "Launch Privileged Container"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.hostname == "worker-node-2"
        assert alert.labels["falco_priority"] == "CRITICAL"
        assert alert.labels["k8s_namespace"] == "production"

    def test_format_alert_suspicious_network(self):
        """Test formatting a suspicious network connection alert."""
        event = {
            "output": "15:45:00.000000000: Error Outbound connection to known C2 server (fd.name=evil.com:443 fd.type=ipv4 fd.sip=1.2.3.4)",
            "priority": "Error",
            "rule": "Contact EC2 Instance Metadata Service from Container",
            "time": "2024-01-15T15:45:00.000000000Z",
            "output_fields": {
                "fd.name": "evil.com:443",
                "fd.sip": "1.2.3.4",
                "fd.type": "ipv4"
            },
            "hostname": "edge-node-1",
            "tags": ["network", "aws", "metadata_service"]
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.name == "Contact EC2 Instance Metadata Service from Container"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.hostname == "edge-node-1"
        assert "network" in alert.tags

    def test_format_alert_no_output_fields(self):
        """Test formatting an alert without output_fields."""
        event = {
            "output": "Simple test alert",
            "priority": "Warning",
            "rule": "Test Rule",
            "time": "2024-01-15T08:00:00Z",
            "hostname": "test-node"
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.name == "Test Rule"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.output_fields == {}
        assert alert.labels["falco_rule"] == "Test Rule"

    def test_format_alert_no_tags(self):
        """Test formatting an alert without tags."""
        event = {
            "output": "Alert without tags",
            "priority": "Informational",
            "rule": "Info Rule",
            "time": "2024-01-15T08:00:00Z",
            "hostname": "test-node"
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.tags == []
        assert alert.severity == AlertSeverity.INFO

    def test_format_alert_no_timestamp(self):
        """Test formatting an alert without timestamp."""
        event = {
            "output": "Alert without time",
            "priority": "Emergency",
            "rule": "Emergency Rule",
            "hostname": "test-node",
            "output_fields": {}
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.lastReceived is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_format_alert_invalid_timestamp(self):
        """Test formatting an alert with invalid timestamp."""
        event = {
            "output": "Alert with bad time",
            "priority": "Alert",
            "rule": "Bad Time Rule",
            "time": "invalid-timestamp",
            "hostname": "test-node"
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.lastReceived is not None
        assert alert.severity == AlertSeverity.CRITICAL

    def test_severity_mapping(self):
        """Test that all priority levels are mapped correctly."""
        test_cases = [
            ("EMERGENCY", AlertSeverity.CRITICAL),
            ("ALERT", AlertSeverity.CRITICAL),
            ("CRITICAL", AlertSeverity.CRITICAL),
            ("ERROR", AlertSeverity.HIGH),
            ("WARNING", AlertSeverity.WARNING),
            ("WARN", AlertSeverity.WARNING),
            ("NOTICE", AlertSeverity.INFO),
            ("INFORMATIONAL", AlertSeverity.INFO),
            ("DEBUG", AlertSeverity.INFO),
            ("UNKNOWN", AlertSeverity.INFO),  # Default
        ]

        for priority, expected_severity in test_cases:
            event = {
                "output": f"Test alert with {priority}",
                "priority": priority,
                "rule": "Test Rule",
                "time": "2024-01-15T08:00:00Z",
                "hostname": "test-node"
            }

            alert = FalcoProvider._format_alert(event)
            assert alert.severity == expected_severity, f"Failed for priority: {priority}"

    def test_format_alert_kubernetes_context(self):
        """Test that Kubernetes context is properly extracted."""
        event = {
            "output": "Kubernetes event",
            "priority": "Warning",
            "rule": "K8s Rule",
            "time": "2024-01-15T08:00:00Z",
            "output_fields": {
                "k8s.ns.name": "kube-system",
                "k8s.pod.name": "coredns-123",
                "k8s.node.name": "master-1",
                "k8s.deployment.name": "coredns"
            },
            "hostname": "k8s-node"
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.labels["k8s_namespace"] == "kube-system"
        assert alert.labels["k8s_pod"] == "coredns-123"
        assert alert.labels["k8s_node"] == "master-1"

    def test_format_alert_process_context(self):
        """Test that process context is properly extracted."""
        event = {
            "output": "Process event",
            "priority": "Notice",
            "rule": "Process Rule",
            "time": "2024-01-15T08:00:00Z",
            "output_fields": {
                "proc.name": "curl",
                "proc.cmdline": "curl -X POST https://example.com",
                "user.name": "www-data"
            },
            "hostname": "app-server"
        }

        alert = FalcoProvider._format_alert(event)

        assert alert.labels["process_name"] == "curl"
        assert alert.labels["process_cmdline"] == "curl -X POST https://example.com"
        assert alert.labels["user_name"] == "www-data"

    def test_alert_id_uniqueness(self):
        """Test that alert IDs are unique based on rule, hostname and timestamp."""
        event1 = {
            "output": "Alert 1",
            "priority": "Warning",
            "rule": "Test Rule",
            "time": "2024-01-15T08:00:00Z",
            "hostname": "node-1"
        }
        event2 = {
            "output": "Alert 2",
            "priority": "Warning",
            "rule": "Test Rule",
            "time": "2024-01-15T08:00:01Z",  # Different timestamp
            "hostname": "node-1"
        }

        alert1 = FalcoProvider._format_alert(event1)
        alert2 = FalcoProvider._format_alert(event2)

        assert alert1.id != alert2.id


if __name__ == "__main__":
    pytest.main([__file__])
