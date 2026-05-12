ALERTS = {
    "Link down trap": {
        "payload": {
            "source_ip": "192.0.2.10",
            "trap_name": "linkDown",
            "trap_oid": "1.3.6.1.6.3.1.1.5.3",
            "varbinds": [
                {
                    "oid": "1.3.6.1.2.1.2.2.1.2",
                    "value": "eth0",
                    "type": "octet_string",
                },
                {
                    "oid": "1.3.6.1.2.1.1.5.0",
                    "value": "edge-router-1",
                    "type": "octet_string",
                },
            ],
        }
    },
    "Link up trap": {
        "payload": {
            "source_ip": "192.0.2.10",
            "trap_name": "linkUp",
            "trap_oid": "1.3.6.1.6.3.1.1.5.4",
            "varbinds": [
                {
                    "oid": "1.3.6.1.2.1.2.2.1.2",
                    "value": "eth0",
                    "type": "octet_string",
                }
            ],
        }
    },
}
