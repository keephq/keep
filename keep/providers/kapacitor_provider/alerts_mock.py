ALERTS = {
    "CpuAlertCritical": {
        "payload": {
            "id": "cpu_alert:host=server01",
            "message": "CPU usage is critically high on server01",
            "details": "CPU usage has exceeded 95% for more than 5 minutes on host server01. Current value: 97.3%",
            "level": "CRITICAL",
            "time": "2024-01-15T10:30:00Z",
            "duration": "5m30s",
            "previousLevel": "WARNING",
            "data": {
                "series": [
                    {
                        "name": "cpu",
                        "tags": {"host": "server01", "region": "us-east-1"},
                        "columns": ["time", "mean_usage_idle"],
                        "values": [
                            ["2024-01-15T10:30:00Z", 2.7]
                        ],
                    }
                ]
            },
        },
    },
    "DiskAlertWarning": {
        "payload": {
            "id": "disk_alert:host=server02",
            "message": "Disk usage warning on server02",
            "details": "Disk usage on /dev/sda1 has exceeded 80%. Current value: 85.2%",
            "level": "WARNING",
            "time": "2024-01-15T11:00:00Z",
            "duration": "15m0s",
            "previousLevel": "INFO",
            "data": {
                "series": [
                    {
                        "name": "disk",
                        "tags": {"host": "server02", "path": "/dev/sda1"},
                        "columns": ["time", "used_percent"],
                        "values": [
                            ["2024-01-15T11:00:00Z", 85.2]
                        ],
                    }
                ]
            },
        },
    },
    "ServiceRecovered": {
        "payload": {
            "id": "service_alert:service=web",
            "message": "Web service has recovered",
            "details": "The web service is responding normally again. Response time: 45ms",
            "level": "OK",
            "time": "2024-01-15T12:00:00Z",
            "duration": "0s",
            "previousLevel": "CRITICAL",
            "data": {
                "series": [
                    {
                        "name": "http_response",
                        "tags": {"service": "web"},
                        "columns": ["time", "response_time"],
                        "values": [
                            ["2024-01-15T12:00:00Z", 0.045]
                        ],
                    }
                ]
            },
        },
    },
}
