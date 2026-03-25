ALERTS = {
    "link_down": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_address": "192.0.2.10",
            "timestamp": "2026-03-25T10:00:00Z",
            "variables": {
                "ifIndex": "12",
                "ifName": "xe-0/0/0",
                "ifDescr": "uplink to core",
            },
        }
    },
    "link_up": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "source_address": "192.0.2.10",
            "timestamp": "2026-03-25T10:01:00Z",
            "variables": {
                "ifIndex": "12",
                "ifName": "xe-0/0/0",
            },
        }
    },
    "cold_start": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "source_address": "198.51.100.7",
            "timestamp": "2026-03-25T10:05:00Z",
            "message": "Device restarted",
        }
    },
    "authentication_failure": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "source_address": "198.51.100.20",
            "timestamp": "2026-03-25T10:08:00Z",
            "description": "Authentication failure reported by edge-fw-01",
        }
    },
    "enterprise_specific": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.8072.2.3.0.1",
            "source_address": "203.0.113.55",
            "timestamp": "2026-03-25T10:15:00Z",
            "trap_name": "customEnterpriseTrap",
            "varbinds": {
                "customSeverity": "minor",
                "customCode": "ABC-123",
            },
        }
    },
}
