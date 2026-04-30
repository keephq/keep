"""
Mock SNMP trap payloads for Keep's alert simulation.

Structure must match what BaseProvider.simulate_alert() expects:
  ALERTS = {
      "AlertTypeName": {
          "payload": { ... }   ← dict passed to _format_alert()
      },
      ...
  }
"""

ALERTS = {
    "linkDown": {
        "payload": {
            "name": "linkDown",
            "oid": "1.3.6.1.6.3.1.1.5.3",
            "generic_trap": 2,
            "agent_address": "10.0.0.1",
            "community": "public",
            "severity": "critical",
            "description": "Interface GigabitEthernet0/1 went down on core-router-01",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.2.1": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.8.1": "2",  # ifOperStatus: down(2)
            },
        },
    },
    "coldStart": {
        "payload": {
            "name": "coldStart",
            "oid": "1.3.6.1.6.3.1.1.5.1",
            "generic_trap": 0,
            "agent_address": "192.168.1.5",
            "community": "public",
            "severity": "warning",
            "description": "Device 192.168.1.5 performed a cold start (unexpected reboot)",
            "varbinds": {},
        },
    },
    "authenticationFailure": {
        "payload": {
            "name": "authenticationFailure",
            "oid": "1.3.6.1.6.3.1.1.5.5",
            "generic_trap": 4,
            "agent_address": "10.10.10.20",
            "community": "public",
            "severity": "high",
            "description": "SNMP authentication failure from 10.10.10.20 – wrong community string",
            "varbinds": {},
        },
    },
    "linkUp": {
        "payload": {
            "name": "linkUp",
            "oid": "1.3.6.1.6.3.1.1.5.4",
            "generic_trap": 3,
            "agent_address": "10.0.0.1",
            "community": "public",
            "severity": "info",
            "description": "Interface GigabitEthernet0/1 is back up on core-router-01",
            "varbinds": {
                "1.3.6.1.2.1.2.2.1.2.1": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.8.1": "1",  # ifOperStatus: up(1)
            },
        },
    },
    "warmStart": {
        "payload": {
            "name": "warmStart",
            "oid": "1.3.6.1.6.3.1.1.5.2",
            "generic_trap": 1,
            "agent_address": "172.16.0.50",
            "community": "public",
            "severity": "info",
            "description": "Device 172.16.0.50 performed a warm start (planned reload)",
            "varbinds": {},
        },
    },
    "cpuThresholdExceeded": {
        "payload": {
            "name": "cpuThresholdExceeded",
            "oid": "1.3.6.1.4.1.9.9.109.2.0.1",
            "generic_trap": 6,
            "agent_address": "10.1.2.3",
            "community": "public",
            "severity": "high",
            "description": "CPU utilisation exceeded 90% threshold on switch-floor2",
            "varbinds": {
                "1.3.6.1.4.1.9.9.109.1.1.1.1.3.1": "91",  # cpmCPUTotal5min
            },
        },
    },
}