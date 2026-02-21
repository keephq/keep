"""Mock SNMP trap data for testing and UI preview."""

ALERTS = {
    "linkDown_v2c": {
        "payload": {
            "version": "v2c",
            "oid": "1.3.6.1.6.3.1.1.5.3",
            "agent_address": "192.168.1.100",
            "community": "public",
            "hostname": "switch01.example.com",
            "description": "Interface GigabitEthernet0/1 is down",
            "varbinds": {
                "1.3.6.1.2.1.1.3.0": "12345678",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.3",
                "1.3.6.1.2.1.2.2.1.1": "1",
                "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.7": "2",
                "1.3.6.1.2.1.2.2.1.8": "2",
            },
        },
    },
    "linkDown_v1": {
        "payload": {
            "version": "v1",
            "enterprise": "1.3.6.1.4.1.9.1",
            "agent_address": "10.0.0.1",
            "generic_trap": 2,
            "specific_trap": 0,
            "hostname": "router01",
            "community": "public",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.1": "3",
                "1.3.6.1.2.1.2.2.1.2": "FastEthernet0/0",
            },
        },
    },
    "linkUp_v1": {
        "payload": {
            "version": "v1",
            "enterprise": "1.3.6.1.4.1.9.1",
            "agent_address": "10.0.0.1",
            "generic_trap": 3,
            "specific_trap": 0,
            "hostname": "router01",
            "community": "public",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.1": "3",
                "1.3.6.1.2.1.2.2.1.2": "FastEthernet0/0",
            },
        },
    },
    "coldStart_v2c": {
        "payload": {
            "version": "v2c",
            "oid": "1.3.6.1.6.3.1.1.5.1",
            "agent_address": "172.16.0.50",
            "community": "monitoring",
            "hostname": "firewall01",
            "varbinds": {
                "1.3.6.1.2.1.1.3.0": "0",
            },
        },
    },
    "authFailure_v2c": {
        "payload": {
            "version": "v2c",
            "oid": "1.3.6.1.6.3.1.1.5.5",
            "agent_address": "192.168.1.50",
            "community": "public",
            "hostname": "server01",
            "description": "SNMP authentication failure from 10.0.0.99",
        },
    },
    "enterprise_v3": {
        "payload": {
            "version": "v3",
            "oid": "1.3.6.1.4.1.2636.4.1.1",
            "agent_address": "10.10.10.1",
            "hostname": "juniper-mx01",
            "severity": "critical",
            "description": "Juniper chassis alarm: FPC 0 Major Errors",
            "varbinds": {
                "1.3.6.1.4.1.2636.3.1.15.1.5.9.1.0.0": "FPC 0 Major Errors",
                "1.3.6.1.4.1.2636.3.1.15.1.6.9.1.0.0": "2",
            },
        },
    },
    "custom_severity": {
        "payload": {
            "version": "v2c",
            "oid": "1.3.6.1.4.1.12345.1.2.3",
            "agent_address": "192.168.100.10",
            "hostname": "app-server-01",
            "severity": "major",
            "description": "Application health check failed",
            "name": "App Health Check Failure",
            "varbinds": {
                "1.3.6.1.4.1.12345.1.2.3.1": "health_check",
                "1.3.6.1.4.1.12345.1.2.3.2": "FAILED",
                "1.3.6.1.4.1.12345.1.2.3.3": "HTTP 503",
            },
        },
    },
}
