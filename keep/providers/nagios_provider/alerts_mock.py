ALERTS = {
    "service_critical": {
        "payload": {
            "notification_type": "PROBLEM",
            "host_name": "web-prod-01",
            "host_alias": "web-prod-01.internal",
            "host_address": "10.0.0.21",
            "service_description": "HTTP",
            "service_state": "CRITICAL",
            "service_output": "HTTP CRITICAL: HTTP/1.1 500 Internal Server Error",
            "long_service_output": "Connection succeeded but server returned 500.",
            "service_check_command": "check_http!-H web-prod-01 -p 80",
            "service_problem_id": "SP-12345",
            "service_attempt": "3",
            "service_duration": "0d 0h 5m 12s",
            "long_date_time": "Sun Mar 15 14:23:42 UTC 2026",
            "contact_name": "oncall",
            "contact_email": "oncall@example.com",
        }
    },
    "host_down": {
        "payload": {
            "notification_type": "PROBLEM",
            "host_name": "db-prod-02",
            "host_alias": "db-prod-02.internal",
            "host_address": "10.0.0.42",
            "host_state": "DOWN",
            "host_output": "PING CRITICAL - 100% packet loss",
            "host_check_command": "check_ping!100.0,20%!500.0,60%",
            "host_problem_id": "HP-9876",
            "host_attempt": "5",
            "host_duration": "0d 0h 2m 03s",
            "long_date_time": "Sun Mar 15 14:25:01 UTC 2026",
        }
    },
    "service_recovery": {
        "payload": {
            "notification_type": "RECOVERY",
            "host_name": "web-prod-01",
            "service_description": "HTTP",
            "service_state": "OK",
            "service_output": "HTTP OK: HTTP/1.1 200 OK - 1234 bytes in 0.045 second response time",
            "service_problem_id": "SP-12345",
            "long_date_time": "Sun Mar 15 14:31:02 UTC 2026",
        }
    },
    "service_warning_acknowledged": {
        "payload": {
            "notification_type": "ACKNOWLEDGEMENT",
            "host_name": "queue-worker-03",
            "service_description": "QueueDepth",
            "service_state": "WARNING",
            "service_output": "Queue depth above warning threshold (1500 > 1000)",
            "service_problem_id": "SP-44455",
            "long_date_time": "Sun Mar 15 14:40:00 UTC 2026",
            "contact_name": "operator",
        }
    },
    "host_recovery": {
        "payload": {
            "notification_type": "RECOVERY",
            "host_name": "db-prod-02",
            "host_state": "UP",
            "host_output": "PING OK - Packet loss = 0%, RTA = 1.42 ms",
            "host_problem_id": "HP-9876",
            "long_date_time": "Sun Mar 15 14:42:18 UTC 2026",
        }
    },
}
