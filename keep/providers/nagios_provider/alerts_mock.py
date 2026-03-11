# Mock webhook payloads for manual testing.
# Use ALERTS for service alerts and HOST_ALERTS for host alerts.

ALERTS = {
    "host_name": "webserver01",
    "host_alias": "Web Server 01",
    "host_address": "192.168.1.100",
    "service_description": "HTTP",
    "state": "CRITICAL",
    "state_type": "HARD",
    "output": "HTTP CRITICAL - Socket timeout after 10 seconds",
    "long_output": "Connection to 192.168.1.100:80 timed out after 10 seconds.",
    "notification_type": "PROBLEM",
    "timestamp": "1710072000",
}

HOST_ALERTS = {
    "host_name": "dbserver02",
    "host_alias": "DB Server 02",
    "host_address": "192.168.1.200",
    "state": "DOWN",
    "state_type": "HARD",
    "output": "PING CRITICAL - Packet loss = 100%",
    "long_output": "No response received from host within timeout period.",
    "notification_type": "PROBLEM",
    "timestamp": "1710072600",
}
