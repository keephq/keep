"""
Mock Nagios webhook payloads for testing.
These payloads simulate what a Nagios notify script would POST to Keep.
Reference: https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/notifications.html
"""

ALERTS = {
    "HostDown": {
        "payload": {
            "check_type": "HOST",
            "hostname": "web-server-01",
            "host_address": "192.168.1.10",
            "state": "DOWN",
            "notification_type": "PROBLEM",
            "plugin_output": "PING CRITICAL - Packet loss = 100%",
            "long_plugin_output": "",
            "check_attempt": 3,
            "max_check_attempts": 3,
        }
    },
    "ServiceCritical": {
        "payload": {
            "check_type": "SERVICE",
            "hostname": "db-server-02",
            "host_address": "192.168.1.20",
            "state": "CRITICAL",
            "service_description": "MySQL",
            "notification_type": "PROBLEM",
            "plugin_output": "CRITICAL: MySQL is not running",
            "long_plugin_output": "Cannot connect to MySQL on 3306: Connection refused",
            "check_attempt": 3,
            "max_check_attempts": 3,
        }
    },
    "ServiceRecovered": {
        "payload": {
            "check_type": "SERVICE",
            "hostname": "app-server-03",
            "host_address": "192.168.1.30",
            "state": "OK",
            "service_description": "HTTP",
            "notification_type": "RECOVERY",
            "plugin_output": "HTTP OK: HTTP/1.1 200 OK - 0.312 second response time",
            "long_plugin_output": "",
            "check_attempt": 1,
            "max_check_attempts": 3,
        }
    },
}
