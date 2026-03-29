"""
Mock SNMP trap alerts for Keep UI and testing.

These fixtures represent typical SNMP traps from network devices.
"""

import datetime
import uuid

MOCK_ALERTS = [
    {
        "id": str(uuid.uuid4()),
        "name": "linkDown",
        "description": "OID: 1.3.6.1.6.3.1.1.5.3\nSource: 192.168.1.1\n1.3.6.1.2.1.2.2.1.1.1: 1",
        "severity": "critical",
        "status": "firing",
        "source": ["snmp"],
        "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "source_address": "192.168.1.1",
        "snmp_version": "2c",
        "vendor": "Unknown",
        "lastReceived": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "labels": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source_address": "192.168.1.1",
            "snmp_version": "2c",
            "vendor": "Unknown",
            "community": "public",
        },
    },
    {
        "id": str(uuid.uuid4()),
        "name": "linkUp",
        "description": "OID: 1.3.6.1.6.3.1.1.5.4\nSource: 192.168.1.1\n1.3.6.1.2.1.2.2.1.1.1: 1",
        "severity": "info",
        "status": "resolved",
        "source": ["snmp"],
        "trap_oid": "1.3.6.1.6.3.1.1.5.4",
        "source_address": "192.168.1.1",
        "snmp_version": "2c",
        "vendor": "Unknown",
        "lastReceived": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "labels": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "source_address": "192.168.1.1",
            "snmp_version": "2c",
            "vendor": "Unknown",
        },
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Cisco Device Alert",
        "description": "OID: 1.3.6.1.4.1.9.9.43.2.0.1\nSource: 10.0.1.1",
        "severity": "high",
        "status": "firing",
        "source": ["snmp"],
        "trap_oid": "1.3.6.1.4.1.9.9.43.2.0.1",
        "source_address": "10.0.1.1",
        "snmp_version": "3",
        "vendor": "Cisco",
        "lastReceived": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "labels": {
            "trap_oid": "1.3.6.1.4.1.9.9.43.2.0.1",
            "source_address": "10.0.1.1",
            "snmp_version": "3",
            "vendor": "Cisco",
        },
    },
]
