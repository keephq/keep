ALERTS = {
    "snmp_link_down_trap": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.1",
            "source": "192.168.1.100",
            "var_binds": {
                "1.3.6.1.2.1.1.3.0": "123456",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.1",
                "1.3.6.1.2.1.2.2.1.1.1": "1",
                "1.3.6.1.2.1.2.2.1.7.1": "down",
            },
            "timestamp": "2024-01-15T10:30:00Z",
            "community": "public",
            "snmp_version": 2,
        },
    },
    "snmp_cold_start_trap": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.2",
            "source": "192.168.1.50",
            "var_binds": {
                "1.3.6.1.2.1.1.3.0": "0",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.2",
                "1.3.6.1.2.1.1.1.0": "Cisco IOS Software",
            },
            "timestamp": "2024-01-15T08:00:00Z",
            "community": "public",
            "snmp_version": 2,
        },
    },
    "snmp_auth_failure_trap": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "source": "10.0.0.1",
            "var_binds": {
                "1.3.6.1.2.1.1.3.0": "987654",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.4",
                "1.3.6.1.6.3.18.1.3.0": "10.0.0.99",
            },
            "timestamp": "2024-01-15T12:00:00Z",
            "community": "private",
            "snmp_version": 1,
        },
    },
    "snmp_enterprise_trap": {
        "payload": {
            "trap_oid": "1.3.6.1.4.1.9.9.41.2.0.1",
            "source": "192.168.1.1",
            "var_binds": {
                "1.3.6.1.2.1.1.3.0": "456789",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.4.1.9.9.41.2.0.1",
                "1.3.6.1.4.1.9.9.41.1.2.3.1": "LINK-3-UPDOWN",
                "1.3.6.1.4.1.9.9.41.1.2.3.2": "6",
                "1.3.6.1.4.1.9.9.41.1.2.3.3": "Interface GigabitEthernet0/1, changed state to up",
            },
            "timestamp": "2024-01-15T14:15:00Z",
            "community": "public",
            "snmp_version": 3,
        },
    },
    "snmp_warm_start_trap": {
        "payload": {
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "source": "172.16.0.1",
            "var_binds": {
                "1.3.6.1.2.1.1.3.0": "100",
                "1.3.6.1.6.3.1.1.4.1.0": "1.3.6.1.6.3.1.1.5.3",
                "1.3.6.1.2.1.1.1.0": "Linux Server 5.15.0",
            },
            "timestamp": "2024-01-15T09:05:00Z",
            "community": "public",
            "snmp_version": 2,
        },
    },
    "snmp_poll_result": {
        "payload": {
            "oid": "1.3.6.1.2.1.1.3.0",
            "value": "123456789",
            "error": None,
            "type": "TimeTicks",
            "host": "192.168.1.1",
            "snmp_version": 2,
        },
    },
}
