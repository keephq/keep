"""
Mock Cribl HTTP output payloads for testing.
Cribl forwards events in the upstream source format, enriched with Cribl metadata.
Reference: https://docs.cribl.io/stream/destinations-http/
"""

ALERTS = {
    "GenericAlert": {
        "payload": {
            "_time": 1705312200.0,
            "host": "prod-worker-01",
            "source": "app-monitor",
            "sourcetype": "json",
            "name": "HighErrorRate",
            "message": "Error rate exceeded threshold: 15% errors in the last 5 minutes",
            "severity": "critical",
            "status": "firing",
            "service": "checkout-service",
            "environment": "production",
        }
    },
    "SplunkHECPassthrough": {
        "payload": {
            "_time": 1705312800.0,
            "host": "web-server-02",
            "sourcetype": "access_combined",
            "source": "/var/log/nginx/access.log",
            "severity": "warning",
            "status": "firing",
            "message": "HTTP 5xx error rate spiking: 203 errors in 60s",
            "index": "main",
        }
    },
    "CriblNotification": {
        "payload": {
            "type": "backpressure",
            "condition": "output_queue_full",
            "value": "98%",
            "description": "HTTP output queue is 98% full — events may be dropped",
            "_time": 1705313400.0,
            "host": "cribl-leader-01",
        }
    },
}
