"""
Mock ElastAlert2 HTTP POST alert payloads for testing.
Payloads represent what ElastAlert2 sends when http_post_all_values: true is set.
Reference: https://elastalert2.readthedocs.io/en/latest/ruletypes.html#http-post
"""

ALERTS = {
    "high_error_rate": {
        "payload": {
            "rule_name": "high-error-rate",
            "alert_subject": "High HTTP 5xx error rate detected",
            "alert_text": "More than 100 HTTP 500 errors in the last 5 minutes on web-server-01.",
            "alert_type": "frequency",
            "@timestamp": "2024-01-15T14:30:00.000Z",
            "severity": "critical",
            "_index": "nginx-logs-2024.01.15",
            "host": {"name": "web-server-01"},
            "http_status": 500,
            "request_path": "/api/v1/users",
            "num_hits": 127,
            "num_matches": 127,
        }
    },
    "failed_logins": {
        "payload": {
            "rule_name": "brute-force-login-attempt",
            "alert_subject": "Multiple failed login attempts detected",
            "alert_text": "50 failed SSH login attempts from 192.168.1.100 in the last 10 minutes.",
            "alert_type": "spike",
            "@timestamp": "2024-01-15T15:00:00.000Z",
            "severity": "high",
            "_index": "auth-logs-2024.01.15",
            "host": {"name": "bastion-01"},
            "source_ip": "192.168.1.100",
            "user": "root",
            "event_type": "authentication_failure",
            "num_hits": 50,
            "num_matches": 50,
        }
    },
    "disk_space_low": {
        "payload": {
            "rule_name": "disk-space-low",
            "alert_subject": "Low disk space on db-server-02",
            "alert_text": "Disk usage on /data has exceeded 90% on db-server-02.",
            "alert_type": "any",
            "@timestamp": "2024-01-15T16:00:00.000Z",
            "severity": "warning",
            "_index": "metricbeat-2024.01.15",
            "host": "db-server-02",
            "disk_path": "/data",
            "disk_used_percent": 91.3,
            "num_hits": 1,
            "num_matches": 1,
        }
    },
}
