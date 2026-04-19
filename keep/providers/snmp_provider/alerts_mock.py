"""
SNMP Provider Alerts Mock - Used for testing purposes.
"""

SNMP_ALERT_GET_RESPONSE = {
    "1.3.6.1.2.1.1.1.0": "Linux 4.19.0-18-amd64 #1 SMP Debian",
    "1.3.6.1.2.1.1.5.0": "router01",
}

SNMP_ALERT_WALK_RESPONSE = {
    "1.3.6.1.2.1.1.1.0": "Linux 4.19.0-18-amd64",
    "1.3.6.1.2.1.1.3.0": "12345",
    "1.3.6.1.2.1.1.5.0": "router01",
    "1.3.6.1.2.1.1.6.0": "1",
}

SNMP_ALERT_INTERFACE_DOWN = {
    "id": "192.168.1.1-if-2",
    "name": "Interface Down: GigabitEthernet0/1",
    "description": "Interface 2 (ethernetCsmacd) is down. Speed: 1000000000",
    "severity": "critical",
    "host": "192.168.1.1",
    "status": "firing",
}

SNMP_ALERT_TRAP_V2C = {
    "oid": "1.3.6.1.4.1.9.9.42.2.0.1",
    "name": "Interface Status Change",
    "description": "Link down on interface 2",
    "severity": "critical",
    "host": "10.0.0.1",
    "SNMPv2-SMI::snmpTrapOID.0": "1.3.6.1.4.1.9.9.42.2.0.1",
}
