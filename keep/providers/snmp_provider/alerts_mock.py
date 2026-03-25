ALERTS = {
    "linkDown": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "trap_name": "linkDown",
            "agent_address": "192.168.1.1",
            "community": "public",
            "snmp_version": "v2c",
            "enterprise": "1.3.6.1.4.1.9.1",
            "uptime": "123456",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.1": "2",
                "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.3": "6",
            },
            "description": "Interface GigabitEthernet0/1 on 192.168.1.1 went down",
            "severity": "critical",
        },
        "parameters": {
            "severity": ["critical", "high", "warning", "info"],
        },
        "renders": {
            "agent_address": [
                "192.168.1.1",
                "192.168.1.2",
                "10.0.0.1",
                "10.0.0.5",
            ],
        },
    },
    "linkUp": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "trap_name": "linkUp",
            "agent_address": "192.168.1.1",
            "community": "public",
            "snmp_version": "v2c",
            "enterprise": "1.3.6.1.4.1.9.1",
            "uptime": "234567",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.1": "2",
                "1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.3": "6",
            },
            "description": "Interface GigabitEthernet0/1 on 192.168.1.1 is up",
            "severity": "info",
        },
        "parameters": {
            "severity": ["info", "warning"],
        },
        "renders": {
            "agent_address": [
                "192.168.1.1",
                "192.168.1.2",
                "10.0.0.1",
            ],
        },
    },
    "coldStart": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "trap_name": "coldStart",
            "agent_address": "10.0.0.50",
            "community": "public",
            "snmp_version": "v2c",
            "enterprise": "1.3.6.1.4.1.9.1",
            "uptime": "0",
            "varbinds": {},
            "description": "Device 10.0.0.50 has restarted (cold start)",
            "severity": "warning",
        },
        "parameters": {
            "severity": ["warning", "info"],
        },
        "renders": {
            "agent_address": [
                "10.0.0.50",
                "10.0.0.51",
                "192.168.10.1",
            ],
        },
    },
    "authenticationFailure": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "trap_name": "authenticationFailure",
            "agent_address": "10.0.0.100",
            "community": "public",
            "snmp_version": "v2c",
            "enterprise": "1.3.6.1.4.1.9.1",
            "uptime": "345678",
            "varbinds": {},
            "description": "SNMP authentication failure on device 10.0.0.100",
            "severity": "high",
        },
        "parameters": {
            "severity": ["high", "critical"],
        },
        "renders": {
            "agent_address": [
                "10.0.0.100",
                "10.0.0.101",
                "172.16.0.1",
            ],
        },
    },
}
