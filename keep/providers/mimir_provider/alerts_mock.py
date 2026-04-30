"""
Mock Mimir Alertmanager webhook payloads for testing.
Format is identical to Prometheus Alertmanager webhooks.
Reference: https://grafana.com/docs/mimir/latest/references/http-api/
"""

ALERTS = {
    "HighCPUUsage": {
        "payload": {
            "receiver": "keep",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighCPUUsage",
                        "severity": "critical",
                        "instance": "web-server-01:9100",
                        "job": "node-exporter",
                        "namespace": "production",
                        "__tenant_id__": "team-platform",
                    },
                    "annotations": {
                        "summary": "CPU usage is above 90%",
                        "description": "CPU usage on web-server-01 has been above 90% for more than 5 minutes.",
                    },
                    "startsAt": "2024-01-15T10:30:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "fingerprint": "a1b2c3d4e5f60001",
                }
            ],
            "groupLabels": {"alertname": "HighCPUUsage"},
            "commonLabels": {"severity": "critical", "job": "node-exporter"},
            "commonAnnotations": {},
            "externalURL": "https://mimir.example.com",
        }
    },
    "DiskSpaceLow": {
        "payload": {
            "receiver": "keep",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "DiskSpaceLow",
                        "severity": "warning",
                        "instance": "db-server-02:9100",
                        "job": "node-exporter",
                        "mountpoint": "/data",
                        "__tenant_id__": "team-database",
                    },
                    "annotations": {
                        "summary": "Disk space is below 20%",
                        "description": "Disk /data on db-server-02 has less than 20% space remaining.",
                    },
                    "startsAt": "2024-01-15T11:00:00Z",
                    "endsAt": "0001-01-01T00:00:00Z",
                    "fingerprint": "b2c3d4e5f6a10002",
                }
            ],
            "groupLabels": {"alertname": "DiskSpaceLow"},
            "commonLabels": {"severity": "warning"},
            "commonAnnotations": {},
            "externalURL": "https://mimir.example.com",
        }
    },
    "HighMemoryUsage_Resolved": {
        "payload": {
            "receiver": "keep",
            "status": "resolved",
            "alerts": [
                {
                    "status": "resolved",
                    "labels": {
                        "alertname": "HighMemoryUsage",
                        "severity": "warning",
                        "instance": "app-server-03:9100",
                        "job": "node-exporter",
                        "__tenant_id__": "team-app",
                    },
                    "annotations": {
                        "summary": "Memory usage resolved",
                        "description": "Memory usage on app-server-03 has returned to normal.",
                    },
                    "startsAt": "2024-01-15T09:00:00Z",
                    "endsAt": "2024-01-15T09:30:00Z",
                    "fingerprint": "c3d4e5f6a1b20003",
                }
            ],
            "groupLabels": {"alertname": "HighMemoryUsage"},
            "commonLabels": {"severity": "warning"},
            "commonAnnotations": {},
            "externalURL": "https://mimir.example.com",
        }
    },
}
