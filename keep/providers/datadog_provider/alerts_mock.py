ALERTS = {
    "high_cpu_usage": {
        "payload": {
            "title": "High CPU Usage",
            "type": "metric alert",
            "query": "avg(last_5m):avg:system.cpu.user{*} by {host} > 90",
            "message": "CPU usage is over 90% on {{host.name}}.",
            "tags": "environment:production, team:backend",
            "priority": "P3",
            "monitor_id": "1234567890",
        },
        "parameters": {
            "tags": [
                "environment:production,team:backend,monitor,service:api",
                "environment:staging,team:backend,monitor,service:api",
            ],
            "priority": ["P2", "P3", "P4"],
        },
    },
    "low_disk_space": {
        "payload": {
            "title": "Low Disk Space",
            "type": "metric alert",
            "query": "avg(last_1h):min:system.disk.free{*} by {host} < 20",
            "message": "Disk space is below 20% on {{host.name}}.",
            "tags": "environment:production,team:database",
            "priority": 4,
            "monitor_id": "1234567891",
        },
        "parameters": {
            "tags": [
                "environment:production,team:analytics,monitor,service:api",
                "environment:staging,team:database,monitor,service:api",
            ],
            "priority": ["P1", "P3", "P4"],
        },
    },
}
