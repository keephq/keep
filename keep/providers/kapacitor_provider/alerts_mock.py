"""
Mock Kapacitor HTTP Post alert payloads for testing.
Payloads match the format documented at:
https://docs.influxdata.com/kapacitor/v1/reference/event_handlers/post/#body
"""

ALERTS = {
    "cpu_critical": {
        "payload": {
            "id": "cpu/cpu-total/alert",
            "message": "cpu alert triggered: cpu usage is critically high",
            "details": "CPU usage_idle has dropped below threshold.",
            "time": "2024-01-15T10:30:00Z",
            "duration": 60000000000,
            "level": "CRITICAL",
            "name": "cpu",
            "taskName": "cpu_alert",
            "data": {
                "series": [
                    {
                        "name": "cpu",
                        "tags": {
                            "cpu": "cpu-total",
                            "host": "web-server-01",
                        },
                        "columns": ["time", "usage_idle"],
                        "values": [["2024-01-15T10:30:00Z", 2.5]],
                    }
                ]
            },
        }
    },
    "disk_warning": {
        "payload": {
            "id": "disk/sda1/alert",
            "message": "disk alert triggered: disk usage above 80%",
            "details": "Disk used_percent exceeded warning threshold.",
            "time": "2024-01-15T11:00:00Z",
            "duration": 0,
            "level": "WARNING",
            "name": "disk",
            "taskName": "disk_alert",
            "data": {
                "series": [
                    {
                        "name": "disk",
                        "tags": {
                            "device": "sda1",
                            "host": "db-server-02",
                            "path": "/",
                        },
                        "columns": ["time", "used_percent"],
                        "values": [["2024-01-15T11:00:00Z", 83.4]],
                    }
                ]
            },
        }
    },
    "cpu_recovered": {
        "payload": {
            "id": "cpu/cpu-total/alert",
            "message": "cpu alert recovered: cpu usage returned to normal",
            "details": "CPU usage_idle is back above threshold.",
            "time": "2024-01-15T10:45:00Z",
            "duration": 900000000000,
            "level": "OK",
            "name": "cpu",
            "taskName": "cpu_alert",
            "data": {
                "series": [
                    {
                        "name": "cpu",
                        "tags": {
                            "cpu": "cpu-total",
                            "host": "web-server-01",
                        },
                        "columns": ["time", "usage_idle"],
                        "values": [["2024-01-15T10:45:00Z", 45.2]],
                    }
                ]
            },
        }
    },
}
