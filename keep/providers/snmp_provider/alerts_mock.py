"""
Mock SNMP trap payloads for testing and development.

These represent the three supported JSON formats:
  1. Structured (preferred) — source_ip + trap_oid + varbinds dict
  2. Flat                   — oid + message + source + severity
  3. snmptrapd-style        — src + enterprise + trap + description
"""

ALERTS = [
    # --------------------------------------------------------------------------
    # Structured JSON — SNMPv2c linkDown (severity: HIGH, status: FIRING)
    # --------------------------------------------------------------------------
    {
        "source_ip": "192.168.1.10",
        "community": "public",
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "trap_name": "linkDown",
        "uptime": "567890",
        "varbinds": {
            "1.3.6.1.2.1.2.2.1.1.2": "2",      # ifIndex
            "1.3.6.1.2.1.2.2.1.7.2": "1",      # ifAdminStatus (up)
            "1.3.6.1.2.1.2.2.1.8.2": "2",      # ifOperStatus (down)
        },
    },
    # --------------------------------------------------------------------------
    # Structured JSON — SNMPv2c linkUp (severity: INFO, status: RESOLVED)
    # --------------------------------------------------------------------------
    {
        "source_ip": "192.168.1.10",
        "community": "public",
        "trap_oid": "1.3.6.1.6.3.1.1.5.4",
        "trap_name": "linkUp",
        "uptime": "568100",
        "varbinds": {
            "1.3.6.1.2.1.2.2.1.1.2": "2",
            "1.3.6.1.2.1.2.2.1.7.2": "1",
            "1.3.6.1.2.1.2.2.1.8.2": "1",      # ifOperStatus (up)
        },
    },
    # --------------------------------------------------------------------------
    # Structured JSON — SNMPv2c coldStart (severity: CRITICAL, status: FIRING)
    # --------------------------------------------------------------------------
    {
        "source_ip": "10.0.0.5",
        "community": "public",
        "trap_oid": "1.3.6.1.6.3.1.1.5.1",
        "trap_name": "coldStart",
        "uptime": "0",
        "varbinds": {},
    },
    # --------------------------------------------------------------------------
    # Structured JSON — SNMPv2c authenticationFailure (severity: WARNING)
    # --------------------------------------------------------------------------
    {
        "source_ip": "192.168.100.1",
        "community": "public",
        "trap_oid": "1.3.6.1.6.3.1.1.5.5",
        "trap_name": "authenticationFailure",
        "uptime": "1234567",
        "varbinds": {},
    },
    # --------------------------------------------------------------------------
    # Flat JSON — enterprise-specific trap from a Cisco device
    # --------------------------------------------------------------------------
    {
        "oid": "1.3.6.1.4.1.9.9.43.2.0.1",
        "message": "Configuration change detected on router-core-01",
        "source": "172.16.0.1",
        "severity": "warning",
    },
    # --------------------------------------------------------------------------
    # snmptrapd-style JSON — generic trap type from net-snmp handler
    # --------------------------------------------------------------------------
    {
        "src": "10.10.0.20",
        "enterprise": "1.3.6.1.4.1.2636.4.1.1",
        "trap": "6",
        "description": "BGP peer 10.10.0.1 changed state to Idle",
    },
]
