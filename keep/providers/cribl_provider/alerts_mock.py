"""
Mock alert payloads for the Cribl provider.

These examples represent the various formats a Cribl HTTP Destination may POST
to Keep's webhook endpoint.
"""

# Single event - log line routed from Cribl pipeline
CRIBL_SINGLE_LOG_EVENT = {
    "id": "evt-001",
    "name": "High error rate detected",
    "description": "Error rate exceeded 5% threshold on service auth-service",
    "severity": "error",
    "status": "firing",
    "source": "cribl-edge",
    "host": "web-01.example.com",
    "service": "auth-service",
    "timestamp": 1700000000,
    "pipeline": "error-detector",
    "worker_group": "prod",
    "_raw": "2024-01-01T00:00:00Z ERROR auth-service: rate=6.2% threshold=5%",
}

# Single event - infrastructure alert
CRIBL_INFRA_ALERT = {
    "id": "infra-alert-9a2b",
    "name": "Disk usage critical",
    "description": "Disk /dev/sda1 at 95% capacity on db-primary.example.com",
    "severity": "critical",
    "status": "active",
    "host": "db-primary.example.com",
    "source": "cribl-stream",
    "namespace": "production",
    "env": "prod",
    "timestamp": 1700001000,
    "_time": 1700001000,
    "worker_group": "prod-workers",
    "pipeline": "infra-monitoring",
}

# Batch payload - array of events
CRIBL_BATCH_EVENTS = [
    {
        "id": "batch-evt-1",
        "name": "CPU spike",
        "severity": "warning",
        "status": "firing",
        "host": "app-01.example.com",
        "source": "cribl-edge",
        "timestamp": 1700002000,
        "pipeline": "system-metrics",
        "_raw": "cpu_usage=87.3 threshold=80.0 host=app-01.example.com",
    },
    {
        "id": "batch-evt-2",
        "name": "Memory exhaustion",
        "severity": "critical",
        "status": "firing",
        "host": "app-02.example.com",
        "source": "cribl-edge",
        "timestamp": 1700002001,
        "pipeline": "system-metrics",
        "_raw": "memory_usage=98.1 threshold=90.0 host=app-02.example.com",
    },
    {
        "id": "batch-evt-3",
        "name": "Network latency resolved",
        "severity": "info",
        "status": "resolved",
        "host": "gw-01.example.com",
        "source": "cribl-edge",
        "timestamp": 1700002002,
        "pipeline": "network-monitor",
        "_raw": "latency_ms=12 previous=450 status=resolved host=gw-01.example.com",
    },
]

# Wrapper object with nested events list
CRIBL_WRAPPED_EVENTS = {
    "worker_group": "us-east",
    "pipeline": "security-events",
    "events": [
        {
            "id": "sec-001",
            "name": "Brute force detected",
            "severity": "critical",
            "status": "firing",
            "host": "auth-proxy.example.com",
            "source": "cribl-stream",
            "timestamp": 1700003000,
            "_raw": "action=block src_ip=192.168.1.100 attempts=15 threshold=10",
        },
        {
            "id": "sec-002",
            "name": "Unusual login location",
            "severity": "warning",
            "status": "firing",
            "host": "sso.example.com",
            "source": "cribl-stream",
            "timestamp": 1700003001,
            "_raw": "user=jdoe location=Unknown previous_location=US-East",
        },
    ],
}

# Minimal event with only raw log line
CRIBL_MINIMAL_RAW_EVENT = {
    "_raw": "2024-01-01T12:00:00.000Z CRITICAL database: connection pool exhausted",
    "_time": 1700004000,
    "host": "db-replica.example.com",
    "cribl_source": "syslog-input",
}

# Resolved / cleared event
CRIBL_RESOLVED_EVENT = {
    "id": "evt-resolve-005",
    "name": "Disk usage critical",
    "description": "Disk /dev/sda1 returned to normal capacity (72%)",
    "severity": "info",
    "status": "cleared",
    "host": "db-primary.example.com",
    "source": "cribl-stream",
    "timestamp": 1700005000,
    "pipeline": "infra-monitoring",
}
