"""Sample SNMP trap payloads used by `SnmpProvider.simulate_alert`."""

TRAPS = {
    "linkDown": {
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "trap_name": "linkDown",
        "source_address": "192.0.2.10",
        "community": "public",
        "version": "2c",
        "variables": {
            "1.3.6.1.2.1.2.2.1.1": "2",
            "1.3.6.1.2.1.2.2.1.7": "2",
        },
        "description": "Interface eth1 went down",
        "severity": "high",
    },
    "linkUp": {
        "trap_oid": "1.3.6.1.6.3.1.1.5.4",
        "trap_name": "linkUp",
        "source_address": "192.0.2.10",
        "community": "public",
        "version": "2c",
        "variables": {"1.3.6.1.2.1.2.2.1.1": "2"},
        "description": "Interface eth1 came back up",
    },
    "coldStart": {
        "trap_oid": "1.3.6.1.6.3.1.1.5.1",
        "trap_name": "coldStart",
        "source_address": "192.0.2.20",
        "community": "public",
        "version": "2c",
        "description": "Device rebooted and reinitialised",
    },
    "authenticationFailure": {
        "trap_oid": "1.3.6.1.6.3.1.1.5.5",
        "trap_name": "authenticationFailure",
        "source_address": "192.0.2.30",
        "community": "public",
        "version": "2c",
        "description": "SNMP authentication failure from 10.0.0.5",
    },
}
