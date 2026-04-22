# Mock SNMP trap data for testing and documentation purposes.
# This represents a typical SNMP v2c trap with varbinds.
ALERTS = [
    {
        "id": "snmp-trap-1",
        "name": "SNMP LinkDown Trap",
        "status": "firing",
        "severity": "high",
        "lastReceived": "2025-04-21T12:00:00.000000Z",
        "environment": "production",
        "service": "network",
        "source": ["snmp"],
        "message": "Link down on interface GigabitEthernet0/1",
        "description": "SNMP trap received: linkDown from 192.168.1.1",
        "snmp_trap": {
            "version": "2c",
            "agent_addr": "192.168.1.1",
            "community": "public",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "trap_name": "linkDown",
            "uptime": 123456,
            "var_binds": {
                "1.3.6.1.2.1.2.2.1.1.1": {"value": 1, "type": "Integer32"},
                "1.3.6.1.2.1.2.2.1.2.1": {"value": "GigabitEthernet0/1", "type": "DisplayString"},
                "1.3.6.1.2.1.2.2.1.8.1": {"value": 2, "type": "Integer32"},
                "1.3.6.1.2.1.2.2.1.7.1": {"value": 2, "type": "Integer32"},
            },
        },
    },
    {
        "id": "snmp-trap-2",
        "name": "SNMP ColdStart Trap",
        "status": "firing",
        "severity": "info",
        "lastReceived": "2025-04-21T12:05:00.000000Z",
        "environment": "production",
        "service": "network",
        "source": ["snmp"],
        "message": "Device 192.168.1.2 cold start",
        "description": "SNMP trap received: coldStart from 192.168.1.2",
        "snmp_trap": {
            "version": "2c",
            "agent_addr": "192.168.1.2",
            "community": "public",
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "trap_name": "coldStart",
            "uptime": 0,
            "var_binds": {
                "1.3.6.1.2.1.1.1.0": {
                    "value": "Cisco IOS Software, C2960 Software",
                    "type": "DisplayString",
                },
                "1.3.6.1.2.1.1.3.0": {"value": 0, "type": "TimeTicks"},
            },
        },
    },
]