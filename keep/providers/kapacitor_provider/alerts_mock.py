"""Mock alert payloads for the Kapacitor provider."""

ALERTS = {
    "CpuCritical": {
        "payload": {
            "id": "cpu_alert:host=web01,cpu=cpu-total",
            "message": "CPU is CRITICAL on web01: cpu_usage_idle=4.0",
            "details": "<html><body><h1>Alert Details</h1></body></html>",
            "time": "2026-03-29T12:34:56.789Z",
            "duration": 60000000000,
            "level": "CRITICAL",
            "data": {
                "series": [
                    {
                        "name": "cpu",
                        "tags": {"host": "web01", "cpu": "cpu-total"},
                        "columns": ["time", "cpu_usage_idle"],
                        "values": [["2026-03-29T12:34:56Z", 4.0]],
                    }
                ]
            },
            "previousLevel": "OK",
            "recoverable": True,
        },
        "parameters": {
            "data.series.0.tags.host": ["web01", "web02", "db01", "db02"],
        },
    },
    "MemoryWarning": {
        "payload": {
            "id": "memory_alert:host=db01",
            "message": "Memory usage is WARNING on db01: used_percent=82.5",
            "details": "",
            "time": "2026-03-29T12:35:10.000Z",
            "duration": 120000000000,
            "level": "WARNING",
            "data": {
                "series": [
                    {
                        "name": "mem",
                        "tags": {"host": "db01"},
                        "columns": ["time", "used_percent"],
                        "values": [["2026-03-29T12:35:10Z", 82.5]],
                    }
                ]
            },
            "previousLevel": "OK",
            "recoverable": True,
        },
        "parameters": {
            "data.series.0.tags.host": ["db01", "db02", "cache01"],
        },
    },
    "DiskSpaceCritical": {
        "payload": {
            "id": "disk_alert:host=storage01,device=sda1,fstype=ext4,path=/data",
            "message": "Disk usage CRITICAL on storage01:/data — used_percent=95.2",
            "details": "",
            "time": "2026-03-29T12:36:00.000Z",
            "duration": 30000000000,
            "level": "CRITICAL",
            "data": {
                "series": [
                    {
                        "name": "disk",
                        "tags": {
                            "host": "storage01",
                            "device": "sda1",
                            "path": "/data",
                        },
                        "columns": ["time", "used_percent"],
                        "values": [["2026-03-29T12:36:00Z", 95.2]],
                    }
                ]
            },
            "previousLevel": "WARNING",
            "recoverable": False,
        },
        "parameters": {
            "data.series.0.tags.host": ["storage01", "storage02"],
            "data.series.0.tags.path": ["/data", "/var", "/tmp"],
        },
    },
    "AlertResolved": {
        "payload": {
            "id": "cpu_alert:host=web01,cpu=cpu-total",
            "message": "CPU is OK on web01: cpu_usage_idle=78.0",
            "details": "",
            "time": "2026-03-29T12:40:00.000Z",
            "duration": 0,
            "level": "OK",
            "data": {
                "series": [
                    {
                        "name": "cpu",
                        "tags": {"host": "web01", "cpu": "cpu-total"},
                        "columns": ["time", "cpu_usage_idle"],
                        "values": [["2026-03-29T12:40:00Z", 78.0]],
                    }
                ]
            },
            "previousLevel": "CRITICAL",
            "recoverable": True,
        },
        "parameters": {
            "data.series.0.tags.host": ["web01", "web02"],
        },
    },
}
