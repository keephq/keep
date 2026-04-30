"""Mock SNMP trap payloads for Keep's alert simulation UI."""

import datetime

_TS = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()

ALERTS: dict[str, dict] = {
    "linkDown": {
        "payload": {
            "host": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "trap_name": "linkDown",
            "snmp_version": "v2c",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.1.2": "2",
                "1.3.6.1.2.1.2.2.1.2.2": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.8.2": "2",
            },
            "environment": "production",
        },
        "parameters": {
            "host": ["192.168.1.1", "10.0.0.1", "172.16.0.254", "10.10.10.1"],
        },
    },
    "linkUp": {
        "payload": {
            "host": "192.168.1.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "trap_name": "linkUp",
            "snmp_version": "v2c",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.1.2": "2",
                "1.3.6.1.2.1.2.2.1.2.2": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.8.2": "1",
            },
            "environment": "production",
        },
        "parameters": {
            "host": ["192.168.1.1", "10.0.0.1"],
        },
    },
    "coldStart": {
        "payload": {
            "host": "10.0.0.1",
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "trap_name": "coldStart",
            "snmp_version": "v2c",
            "varbinds": {
                "1.3.6.1.2.1.1.3.0": "0",
            },
            "environment": "production",
        },
        "parameters": {
            "host": ["10.0.0.1", "10.1.1.1", "192.168.0.254"],
        },
    },
    "authenticationFailure": {
        "payload": {
            "host": "192.168.10.5",
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "trap_name": "authenticationFailure",
            "snmp_version": "v2c",
            "varbinds": {
                "1.3.6.1.6.3.18.1.3.0": "192.168.10.5",
                "1.3.6.1.6.3.18.1.4.0": "wrongcommunity",
            },
            "environment": "production",
        },
        "parameters": {
            "host": ["192.168.10.5", "10.20.30.40"],
        },
    },
    "enterpriseTrap": {
        "payload": {
            "host": "10.1.2.3",
            "trap_oid": "1.3.6.1.4.1.9.9.43.2.0.1",
            "trap_name": "1.3.6.1.4.1.9.9.43.2.0.1",
            "snmp_version": "v2c",
            "varbinds": {
                "1.3.6.1.4.1.9.9.43.1.1.6.1.2.1": "running-config",
                "1.3.6.1.4.1.9.9.43.1.1.6.1.3.1": "1",
            },
            "environment": "production",
        },
        "parameters": {
            "host": ["10.1.2.3", "172.20.0.1"],
        },
    },
}
