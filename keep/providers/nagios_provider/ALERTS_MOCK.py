ALERTS_MOCK = [
    # Service CRITICAL
    {
        "host_name": "web-server-01",
        "service_description": "HTTP",
        "service_state": "CRITICAL",
        "output": "CRITICAL - Socket timeout after 10 seconds",
        "timestamp": "2025-01-15T10:30:00Z",
        "notification_type": "PROBLEM",
    },
    # Service WARNING
    {
        "host_name": "db-server-01",
        "service_description": "Disk Usage",
        "service_state": "WARNING",
        "output": "WARNING - Disk usage at 85%",
        "timestamp": "2025-01-15T10:35:00Z",
        "notification_type": "PROBLEM",
    },
    # Service RECOVERY
    {
        "host_name": "web-server-01",
        "service_description": "HTTP",
        "service_state": "OK",
        "output": "OK - HTTP response time 0.5s",
        "timestamp": "2025-01-15T10:40:00Z",
        "notification_type": "RECOVERY",
    },
    # Host DOWN
    {
        "host_name": "app-server-02",
        "host_state": "DOWN",
        "output": "CRITICAL - Host unreachable (10.0.1.5)",
        "timestamp": "2025-01-15T10:45:00Z",
        "notification_type": "PROBLEM",
    },
    # Host RECOVERY
    {
        "host_name": "app-server-02",
        "host_state": "UP",
        "output": "OK - Host is alive",
        "timestamp": "2025-01-15T10:50:00Z",
        "notification_type": "RECOVERY",
    },
    # Acknowledgement
    {
        "host_name": "web-server-01",
        "service_description": "HTTP",
        "service_state": "CRITICAL",
        "output": "CRITICAL - Socket timeout",
        "timestamp": "2025-01-15T10:55:00Z",
        "notification_type": "ACKNOWLEDGEMENT",
    },
    # Host UNREACHABLE
    {
        "host_name": "remote-office-gw",
        "host_state": "UNREACHABLE",
        "output": "CRITICAL - Network path unreachable",
        "timestamp": "2025-01-15T11:00:00Z",
        "notification_type": "PROBLEM",
    },
    # Service UNKNOWN
    {
        "host_name": "monitoring-server",
        "service_description": "SNMP Check",
        "service_state": "UNKNOWN",
        "output": "UNKNOWN - SNMP timeout",
        "timestamp": "2025-01-15T11:05:00Z",
        "notification_type": "PROBLEM",
    },
]
