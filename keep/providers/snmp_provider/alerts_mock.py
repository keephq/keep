"""
Mock SNMP trap alerts for testing and simulation.
"""

ALERTS = {
    "linkDown": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "name": "linkDown",
            "source_ip": "192.168.1.1",
            "message": "Interface eth0 is down",
            "var_binds": {
                "ifIndex": "1",
                "ifDescr": "eth0",
                "ifAdminStatus": "up",
                "ifOperStatus": "down",
            },
        },
    },
    "linkUp": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "name": "linkUp",
            "source_ip": "192.168.1.1",
            "message": "Interface eth0 is up",
            "var_binds": {
                "ifIndex": "1",
                "ifDescr": "eth0",
                "ifAdminStatus": "up",
                "ifOperStatus": "up",
            },
        },
    },
    "coldStart": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "name": "coldStart",
            "source_ip": "192.168.1.2",
            "message": "Device rebooted - cold start",
            "var_binds": {
                "sysUpTime": "0",
                "sysDescr": "Network Switch Model XYZ",
                "sysName": "core-switch-01",
            },
        },
    },
    "warmStart": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.2",
            "name": "warmStart",
            "source_ip": "192.168.1.2",
            "message": "Device warm restart",
            "var_binds": {
                "sysUpTime": "100",
                "sysDescr": "Network Switch Model XYZ",
                "sysName": "core-switch-01",
            },
        },
    },
    "authenticationFailure": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.5",
            "name": "authenticationFailure",
            "source_ip": "192.168.1.100",
            "message": "SNMP authentication failure from unauthorized host",
            "var_binds": {
                "snmpTrapCommunity": "wrong_community",
                "snmpTrapAddress": "10.0.0.50",
            },
        },
    },
    "enterpriseTrap": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.9.9.13.1.3.0.1",
            "name": "ciscoEnvMonTemperatureNotification",
            "source_ip": "192.168.1.10",
            "message": "Temperature threshold exceeded on device",
            "var_binds": {
                "ciscoEnvMonTemperatureStatusDescr": "CPU Temperature",
                "ciscoEnvMonTemperatureStatusValue": "85",
                "ciscoEnvMonTemperatureThreshold": "75",
                "ciscoEnvMonTemperatureState": "warning",
            },
        },
    },
    "cpuHighUtilization": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.2021.10.1.5.1",
            "name": "cpuHighUtilization",
            "source_ip": "192.168.1.20",
            "message": "CPU utilization exceeded threshold",
            "var_binds": {
                "laLoad": "95.5",
                "laLoadInt": "9550",
                "laNames": "Load-1",
                "laConfig": "12",
            },
        },
    },
    "diskSpaceLow": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.2021.9.1.100.1",
            "name": "diskSpaceLow",
            "source_ip": "192.168.1.30",
            "message": "Disk space running low on /var partition",
            "var_binds": {
                "dskPath": "/var",
                "dskDevice": "/dev/sda1",
                "dskTotal": "104857600",
                "dskAvail": "5242880",
                "dskUsed": "99614720",
                "dskPercent": "95",
            },
        },
    },
    "memoryLow": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.2021.4.100.1",
            "name": "memoryLow",
            "source_ip": "192.168.1.40",
            "message": "System memory is critically low",
            "var_binds": {
                "memTotalReal": "16777216",
                "memAvailReal": "524288",
                "memTotalFree": "524288",
                "memShared": "0",
                "memBuffer": "262144",
                "memCached": "1048576",
            },
        },
    },
    "bgpPeerDown": {
        "payload": {
            "trap_oid": "1.3.6.1.2.1.15.7.1",
            "name": "bgpBackwardTransition",
            "source_ip": "192.168.1.254",
            "message": "BGP peer session went down",
            "var_binds": {
                "bgpPeerRemoteAddr": "10.0.0.1",
                "bgpPeerState": "idle",
                "bgpPeerLastError": "Hold Timer Expired",
                "bgpPeerFsmEstablishedTransitions": "5",
            },
        },
    },
    "ospfNeighborDown": {
        "payload": {
            "trap_oid": "1.3.6.1.2.1.14.16.2.2",
            "name": "ospfNbrStateChange",
            "source_ip": "192.168.1.254",
            "message": "OSPF neighbor state changed to Down",
            "var_binds": {
                "ospfRouterId": "192.168.1.254",
                "ospfNbrIpAddr": "192.168.1.253",
                "ospfNbrRtrId": "192.168.1.253",
                "ospfNbrState": "down",
            },
        },
    },
    "powerSupplyFailure": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.9.9.117.2.0.1",
            "name": "cefcPowerSupplyOutputChange",
            "source_ip": "192.168.1.5",
            "message": "Power supply unit failed",
            "var_binds": {
                "cefcFRUPowerOperStatus": "failed",
                "entPhysicalName": "PSU-1",
                "entPhysicalDescr": "Power Supply Unit 1",
            },
        },
    },
    "fanFailure": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.9.9.117.2.0.2",
            "name": "cefcFanTrayStatusChange",
            "source_ip": "192.168.1.5",
            "message": "Fan unit failure detected",
            "var_binds": {
                "cefcFanTrayOperStatus": "failed",
                "entPhysicalName": "FAN-1",
                "entPhysicalDescr": "Fan Tray 1",
            },
        },
    },
}
