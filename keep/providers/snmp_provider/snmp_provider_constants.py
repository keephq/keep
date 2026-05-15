"""
SNMP Provider constants: OID-to-severity mappings and well-known trap OIDs.
"""

from keep.api.models.alert import AlertSeverity

# Generic trap OIDs (SNMPv2-MIB / RFC 3418)
SNMP_TRAP_OID_TO_SEVERITY = {
    "1.3.6.1.6.3.1.1.5.1": AlertSeverity.INFO,      # coldStart
    "1.3.6.1.6.3.1.1.5.2": AlertSeverity.INFO,      # warmStart
    "1.3.6.1.6.3.1.1.5.3": AlertSeverity.CRITICAL,  # linkDown
    "1.3.6.1.6.3.1.1.5.4": AlertSeverity.INFO,      # linkUp
    "1.3.6.1.6.3.1.1.5.5": AlertSeverity.WARNING,   # authenticationFailure
    "1.3.6.1.6.3.1.1.5.6": AlertSeverity.WARNING,   # egpNeighborLoss
}

# Generic-trap integers for SNMPv1 PDUs
SNMPV1_GENERIC_TRAP_TO_SEVERITY = {
    0: AlertSeverity.INFO,      # coldStart
    1: AlertSeverity.INFO,      # warmStart
    2: AlertSeverity.CRITICAL,  # linkDown
    3: AlertSeverity.INFO,      # linkUp
    4: AlertSeverity.WARNING,   # authenticationFailure
    5: AlertSeverity.WARNING,   # egpNeighborLoss
    6: AlertSeverity.INFO,      # enterpriseSpecific (fallback)
}

# Well-known trap OID to human-readable name
SNMP_TRAP_OID_TO_NAME = {
    "1.3.6.1.6.3.1.1.5.1": "coldStart",
    "1.3.6.1.6.3.1.1.5.2": "warmStart",
    "1.3.6.1.6.3.1.1.5.3": "linkDown",
    "1.3.6.1.6.3.1.1.5.4": "linkUp",
    "1.3.6.1.6.3.1.1.5.5": "authenticationFailure",
    "1.3.6.1.6.3.1.1.5.6": "egpNeighborLoss",
}

# SNMPv1 generic-trap integers to human-readable name
SNMPV1_GENERIC_TRAP_TO_NAME = {
    0: "coldStart",
    1: "warmStart",
    2: "linkDown",
    3: "linkUp",
    4: "authenticationFailure",
    5: "egpNeighborLoss",
    6: "enterpriseSpecific",
}

# The snmpTrapOID.0 OID used in SNMPv2c/v3 trap varbinds
SNMP_TRAP_OID_VARBIND = "1.3.6.1.6.3.1.1.4.1.0"

# sysUpTime.0 OID
SYS_UPTIME_OID = "1.3.6.1.2.1.1.3.0"

# ifIndex OID prefix (used to extract interface index from varbinds)
IF_INDEX_OID_PREFIX = "1.3.6.1.2.1.2.2.1.1"

# linkDown trap OID (for resolution pairing)
LINK_DOWN_TRAP_OID = "1.3.6.1.6.3.1.1.5.3"

# linkUp trap OID (for resolution pairing)
LINK_UP_TRAP_OID = "1.3.6.1.6.3.1.1.5.4"
