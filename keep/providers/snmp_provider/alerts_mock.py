"""
Mock SNMP trap data for testing the SNMP provider.

These dicts simulate what _handle_trap would push to Keep via _push_alert(),
and also what a webhook push might look like. They are usable in unit tests or
the Keep provider testing harness.
"""

# ---------------------------------------------------------------------------
# Simulated v2c linkDown trap
# ---------------------------------------------------------------------------
MOCK_TRAP_LINK_DOWN = {
    "id": "a1b2c3d4-0001-4000-8000-000000000001",
    "name": "linkDown",
    "description": (
        "SNMP Trap: linkDown | Trap OID: 1.3.6.1.6.3.1.1.5.3 | "
        "sysUpTime: 123456 | "
        "VarBinds: 1.3.6.1.2.1.2.2.1.1.3=3, 1.3.6.1.2.1.2.2.1.2.3=GigabitEthernet0/1, "
        "1.3.6.1.2.1.2.2.1.8.3=down"
    ),
    "status": "firing",
    "severity": "high",
    "lastReceived": "2025-05-03T22:00:00+00:00",
    "source": ["snmp"],
    "labels": {
        "sysUpTime": "123456",
        "1.3.6.1.2.1.2.2.1.1.3": "3",
        "1.3.6.1.2.1.2.2.1.2.3": "GigabitEthernet0/1",
        "1.3.6.1.2.1.2.2.1.8.3": "down",
    },
    "environment": "production",
}

# ---------------------------------------------------------------------------
# Simulated v2c linkUp trap (link recovered)
# ---------------------------------------------------------------------------
MOCK_TRAP_LINK_UP = {
    "id": "a1b2c3d4-0002-4000-8000-000000000002",
    "name": "linkUp",
    "description": (
        "SNMP Trap: linkUp | Trap OID: 1.3.6.1.6.3.1.1.5.4 | "
        "sysUpTime: 124000 | "
        "VarBinds: 1.3.6.1.2.1.2.2.1.1.3=3, 1.3.6.1.2.1.2.2.1.2.3=GigabitEthernet0/1, "
        "1.3.6.1.2.1.2.2.1.8.3=up"
    ),
    "status": "resolved",
    "severity": "info",
    "lastReceived": "2025-05-03T22:01:00+00:00",
    "source": ["snmp"],
    "labels": {
        "sysUpTime": "124000",
        "1.3.6.1.2.1.2.2.1.1.3": "3",
        "1.3.6.1.2.1.2.2.1.2.3": "GigabitEthernet0/1",
        "1.3.6.1.2.1.2.2.1.8.3": "up",
    },
    "environment": "production",
}

# ---------------------------------------------------------------------------
# Simulated v1 coldStart trap
# ---------------------------------------------------------------------------
MOCK_TRAP_COLD_START = {
    "id": "a1b2c3d4-0003-4000-8000-000000000003",
    "name": "coldStart",
    "description": (
        "SNMP Trap: coldStart | Trap OID: 1.3.6.1.6.3.1.1.5.1 | "
        "sysUpTime: 0"
    ),
    "status": "firing",
    "severity": "critical",
    "lastReceived": "2025-05-03T22:05:00+00:00",
    "source": ["snmp"],
    "labels": {"sysUpTime": "0"},
    "environment": "production",
}

# ---------------------------------------------------------------------------
# Simulated v3 authenticationFailure trap
# ---------------------------------------------------------------------------
MOCK_TRAP_AUTH_FAILURE = {
    "id": "a1b2c3d4-0004-4000-8000-000000000004",
    "name": "authenticationFailure",
    "description": (
        "SNMP Trap: authenticationFailure | Trap OID: 1.3.6.1.6.3.1.1.5.5 | "
        "sysUpTime: 987654 | "
        "VarBinds: 1.3.6.1.6.3.18.1.3.0=192.168.1.100"
    ),
    "status": "firing",
    "severity": "warning",
    "lastReceived": "2025-05-03T22:10:00+00:00",
    "source": ["snmp"],
    "labels": {
        "sysUpTime": "987654",
        "1.3.6.1.6.3.18.1.3.0": "192.168.1.100",
    },
    "environment": "production",
}

# ---------------------------------------------------------------------------
# Simulated enterprise-specific trap
# ---------------------------------------------------------------------------
MOCK_TRAP_ENTERPRISE = {
    "id": "a1b2c3d4-0005-4000-8000-000000000005",
    "name": "1.3.6.1.4.1.9.9.41.2.0.1",
    "description": (
        "SNMP Trap: 1.3.6.1.4.1.9.9.41.2.0.1 | "
        "Trap OID: 1.3.6.1.4.1.9.9.41.2.0.1 | "
        "sysUpTime: 5000 | "
        "VarBinds: 1.3.6.1.4.1.9.9.41.1.2.3.1.2.1=CISCO_CONFIG_EVENT, "
        "1.3.6.1.4.1.9.9.41.1.2.3.1.3.1=5, "
        "1.3.6.1.4.1.9.9.41.1.2.3.1.4.1=Config saved to NVRAM"
    ),
    "status": "firing",
    "severity": "warning",
    "lastReceived": "2025-05-03T22:15:00+00:00",
    "source": ["snmp"],
    "labels": {
        "sysUpTime": "5000",
        "1.3.6.1.4.1.9.9.41.1.2.3.1.2.1": "CISCO_CONFIG_EVENT",
        "1.3.6.1.4.1.9.9.41.1.2.3.1.3.1": "5",
        "1.3.6.1.4.1.9.9.41.1.2.3.1.4.1": "Config saved to NVRAM",
    },
    "environment": "production",
}

# ---------------------------------------------------------------------------
# Simulated SNMP poll result (OID query)
# ---------------------------------------------------------------------------
MOCK_POLL_RESULT = {
    "id": "a1b2c3d4-0006-4000-8000-000000000006",
    "name": "SNMP Poll: 1.3.6.1.2.1.1.1.0",
    "description": "OID 1.3.6.1.2.1.1.1.0 = Cisco IOS Software, C3750E Software",
    "status": "firing",
    "severity": "info",
    "lastReceived": "2025-05-03T22:20:00+00:00",
    "source": ["snmp"],
    "labels": {
        "oid": "1.3.6.1.2.1.1.1.0",
        "value": "Cisco IOS Software, C3750E Software",
    },
    "environment": "production",
}

# ---------------------------------------------------------------------------
# All mock alerts in a single list for easy iteration
# ---------------------------------------------------------------------------
ALL_MOCK_ALERTS = [
    MOCK_TRAP_LINK_DOWN,
    MOCK_TRAP_LINK_UP,
    MOCK_TRAP_COLD_START,
    MOCK_TRAP_AUTH_FAILURE,
    MOCK_TRAP_ENTERPRISE,
    MOCK_POLL_RESULT,
]