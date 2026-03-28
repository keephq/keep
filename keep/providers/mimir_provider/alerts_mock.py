"""
Mock alert payloads for the Mimir provider.

These are used by simulate_alert() to generate realistic test alerts
that match the Alertmanager webhook format used by Grafana Mimir.
"""

ALERTS = {
    "HighCPUUsage": {
        "payload": {
            "summary": "CPU usage is over 90%",
            "labels": {
                "instance": "example1",
                "job": "node",
                "severity": "critical",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.service": ["api", "worker", "scheduler", "db", "cache"],
            "labels.instance": ["10.0.0.1:9100", "10.0.0.2:9100", "10.0.0.3:9100"],
            "labels.namespace": ["production", "staging"],
        },
    },
    "HighMemoryUsage": {
        "payload": {
            "summary": "Memory usage is over 85%",
            "labels": {
                "instance": "example1",
                "job": "node",
                "severity": "warning",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.service": ["api", "worker", "kafka", "elasticsearch"],
            "labels.instance": ["10.0.0.1:9100", "10.0.0.2:9100"],
            "labels.namespace": ["production", "staging", "dev"],
        },
    },
    "DiskSpaceLow": {
        "payload": {
            "summary": "Disk space is below 20%",
            "labels": {
                "instance": "example1",
                "job": "node",
                "severity": "warning",
            },
        },
        "parameters": {
            "labels.mountpoint": ["/", "/data", "/var/log"],
            "labels.device": ["/dev/sda1", "/dev/nvme0n1p1"],
            "labels.instance": ["10.0.0.1:9100", "10.0.0.2:9100"],
        },
    },
    "PodCrashLooping": {
        "payload": {
            "summary": "Pod is crash-looping",
            "labels": {
                "severity": "critical",
                "job": "kube-state-metrics",
            },
        },
        "parameters": {
            "labels.pod": ["api-pod-xyz", "worker-pod-abc", "scheduler-pod-def"],
            "labels.namespace": ["production", "staging"],
            "labels.container": ["api", "worker", "sidecar"],
        },
    },
    "HighErrorRate": {
        "payload": {
            "summary": "HTTP error rate exceeds 5%",
            "labels": {
                "severity": "critical",
                "job": "api",
            },
        },
        "parameters": {
            "labels.service": ["checkout", "payments", "auth", "catalog"],
            "labels.method": ["GET", "POST", "PUT"],
            "labels.status_code": ["500", "503", "504"],
        },
    },
    "SlowQueryLatency": {
        "payload": {
            "summary": "P99 query latency exceeds 2 seconds",
            "labels": {
                "severity": "warning",
                "job": "mysql",
            },
        },
        "parameters": {
            "labels.database": ["orders", "users", "inventory"],
            "labels.instance": ["mysql-primary:3306", "mysql-replica:3306"],
        },
    },
}
