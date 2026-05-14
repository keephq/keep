ALERTS = {
    "link_down": {
        "payload": {
            "version": "2c",
            "source_ip": "10.0.0.15",
            "agent_address": "10.0.0.15",
            "community": "public",
            "enterprise_oid": "1.3.6.1.4.1.8072.3.2.10",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "generic_trap": "linkDown",
            "specific_trap": 0,
            "timestamp": "2026-05-14T12:00:00Z",
            "varbinds": [
                {
                    "oid": "1.3.6.1.2.1.2.2.1.2.1",
                    "name": "ifDescr",
                    "value": "eth0",
                },
                {
                    "oid": "1.3.6.1.2.1.2.2.1.8.1",
                    "name": "ifOperStatus",
                    "value": "down",
                },
            ],
        }
    },
    "link_up": {
        "payload": {
            "version": "2c",
            "host": "router-1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "generic_trap": "linkUp",
            "timestamp": "2026-05-14T12:05:00Z",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.2.1": "eth0",
                "1.3.6.1.2.1.2.2.1.8.1": "up",
            },
        }
    },
    "authentication_failure": {
        "payload": {
            "hostname": "core-switch-1",
            "snmpTrapOID": "1.3.6.1.6.3.1.1.5.5",
            "genericTrap": "authenticationFailure",
            "received_at": "2026-05-14T12:10:00Z",
            "varbinds": [
                ["1.3.6.1.6.3.18.1.3.0", "10.0.0.40"],
            ],
        }
    },
    "enterprise_specific": {
        "payload": {
            "agent": "ups-01",
            "enterprise_oid": "1.3.6.1.4.1.318",
            "trapOid": "1.3.6.1.4.1.318.0.5",
            "generic_trap": "enterpriseSpecific",
            "severity": "warning",
            "timestamp": "2026-05-14T12:15:00Z",
            "varbinds": [
                {
                    "oid": "1.3.6.1.4.1.318.1.1.1.2.2.2.0",
                    "name": "upsBatteryStatus",
                    "value": "batteryLow",
                }
            ],
        }
    },
}
