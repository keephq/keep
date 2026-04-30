ALERTS = [
    {
        "oid": "1.3.6.1.6.3.1.1.5.3",
        "host": "192.168.1.10",
        "message": "linkDown on interface eth0",
        "severity": "high",
        "uptime": "3:14:15.00",
        "variables": {
            "1.3.6.1.2.1.2.2.1.1.2": "2",
            "1.3.6.1.2.1.2.2.1.7.2": "1",
            "1.3.6.1.2.1.2.2.1.8.2": "2",
        },
    },
    {
        "oid": "1.3.6.1.6.3.1.1.5.1",
        "host": "10.0.0.5",
        "message": "coldStart: device rebooted",
        "uptime": "0:00:00.00",
    },
    {
        "oid": "1.3.6.1.4.1.9.9.41.2",
        "host": "switch-core-01.example.com",
        "message": "Enterprise-specific trap: CPU threshold exceeded (95%)",
        "severity": "critical",
        "variables": {
            "1.3.6.1.4.1.9.9.41.1.2.3.1.5": "95",
            "1.3.6.1.4.1.9.9.41.1.2.3.1.6": "80",
        },
    },
]
