ALERTS = {
    "version": "4",
    "groupKey": '{}:{alertname="HighMemoryUsage"}',
    "truncatedAlerts": 0,
    "status": "firing",
    "receiver": "keep",
    "groupLabels": {
        "alertname": "HighMemoryUsage"
    },
    "commonLabels": {
        "alertname": "HighMemoryUsage",
        "job": "node-exporter",
        "severity": "critical"
    },
    "commonAnnotations": {
        "summary": "High memory usage on instance",
        "description": "Memory usage has exceeded 90% for more than 5 minutes."
    },
    "externalURL": "http://alertmanager:9093",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "HighMemoryUsage",
                "instance": "server-01:9100",
                "job": "node-exporter",
                "severity": "critical"
            },
            "annotations": {
                "summary": "High memory usage on server-01",
                "description": "Memory usage on server-01 has exceeded 90% for more than 5 minutes."
            },
            "startsAt": "2025-01-26T10:00:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph?g0.expr=node_memory_MemAvailable_bytes+%2F+node_memory_MemTotal_bytes+%3C+0.1",
            "fingerprint": "a1b2c3d4e5f60001"
        },
        {
            "status": "firing",
            "labels": {
                "alertname": "HighMemoryUsage",
                "instance": "server-02:9100",
                "job": "node-exporter",
                "severity": "critical"
            },
            "annotations": {
                "summary": "High memory usage on server-02",
                "description": "Memory usage on server-02 has exceeded 90% for more than 5 minutes."
            },
            "startsAt": "2025-01-26T10:05:00.000Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "generatorURL": "http://prometheus:9090/graph?g0.expr=node_memory_MemAvailable_bytes+%2F+node_memory_MemTotal_bytes+%3C+0.1",
            "fingerprint": "a1b2c3d4e5f60002"
        }
    ]
}
