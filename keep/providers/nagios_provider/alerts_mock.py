ALERTS = {
    "host_down": {
        "host_name": "db01.example.com",
        "host_state": "DOWN",
        "host_output": "CRITICAL - Host unreachable",
        "notification_type": "PROBLEM",
        "timestamp": "2026-03-09T09:00:00Z",
    },
    "service_critical": {
        "host_name": "web01.example.com",
        "host_state": "UP",
        "host_output": "PING OK - Packet loss = 0%, RTA = 0.23 ms",
        "service_description": "HTTP",
        "service_state": "CRITICAL",
        "service_output": "CRITICAL - HTTP 500 returned from /healthz",
        "notification_type": "PROBLEM",
        "timestamp": "2026-03-09T09:05:00Z",
    },
}
