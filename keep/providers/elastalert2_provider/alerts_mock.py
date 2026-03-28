"""
Mock alert payloads for the ElastAlert2 provider.

These represent typical payloads sent by ElastAlert2's http_post alerter,
matching the structure documented at:
https://elastalert2.readthedocs.io/en/latest/ruletypes.html#http-post
"""

ALERTS = {
    "HighErrorRate": {
        "payload": {
            "rule_name": "HighErrorRate",
            "alert_text": "Error rate exceeded threshold: 150 errors in the last 5 minutes",
            "alert_text_type": "alert_text_only",
            "num_hits": 150,
            "num_matches": 1,
            "@timestamp": "2024-01-15T10:30:00Z",
            "log.level": "error",
            "environment": "production",
            "service": "api-gateway",
        },
        "parameters": {
            "num_hits": [50, 100, 150, 200],
            "service": ["api-gateway", "auth-service", "payment-service", "user-service"],
            "environment": ["production", "staging"],
        },
    },
    "SecurityAnomalyDetected": {
        "payload": {
            "rule_name": "SecurityAnomalyDetected",
            "alert_text": "Unusual authentication pattern detected from IP 10.0.0.1",
            "alert_text_type": "alert_text_only",
            "num_hits": 25,
            "num_matches": 1,
            "@timestamp": "2024-01-15T11:00:00Z",
            "log.level": "critical",
            "source.ip": "10.0.0.1",
            "event.category": "authentication",
            "event.outcome": "failure",
        },
        "parameters": {
            "source.ip": ["10.0.0.1", "192.168.1.100", "172.16.0.50"],
            "num_hits": [5, 10, 25, 50],
        },
    },
    "DiskSpaceWarning": {
        "payload": {
            "rule_name": "DiskSpaceWarning",
            "alert_text": "Disk usage on /data partition exceeded 85%",
            "alert_text_type": "alert_text_only",
            "num_hits": 1,
            "num_matches": 1,
            "@timestamp": "2024-01-15T09:00:00Z",
            "log.level": "warning",
            "host.name": "prod-worker-01",
            "disk.usage_percent": "87",
            "disk.mount_point": "/data",
        },
        "parameters": {
            "host.name": ["prod-worker-01", "prod-worker-02", "prod-db-01"],
            "disk.usage_percent": ["85", "87", "90", "95"],
            "disk.mount_point": ["/", "/data", "/var/log"],
        },
    },
    "SlowQueryAlert": {
        "payload": {
            "rule_name": "SlowQueryAlert",
            "alert_text": "Database query exceeded 5 second threshold",
            "alert_text_type": "alert_text_only",
            "num_hits": 8,
            "num_matches": 1,
            "@timestamp": "2024-01-15T12:00:00Z",
            "log.level": "warning",
            "db.statement": "SELECT * FROM orders WHERE ...",
            "db.duration_ms": "5250",
            "service": "order-service",
        },
        "parameters": {
            "db.duration_ms": ["5100", "6000", "8500", "12000"],
            "service": ["order-service", "reporting-service", "analytics-service"],
        },
    },
}
