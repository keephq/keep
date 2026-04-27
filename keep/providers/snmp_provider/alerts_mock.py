ALERTS = {
    "linkDown": {
        "payload": {
            "name": "linkDown",
            "description": "1.3.6.1.2.1.2.2.1.2.2 = GigabitEthernet0/1",
            "message": "1.3.6.1.2.1.2.2.1.2.2 = GigabitEthernet0/1",
            "status": "firing",
            "severity": "high",
            "source": ["snmp"],
            "service": "10.0.0.1",
            "labels": {
                "1.3.6.1.2.1.2.2.1.2.2": "GigabitEthernet0/1",
                "1.3.6.1.2.1.2.2.1.7.2": "1",
            },
        },
        "parameters": {
            "labels.1.3.6.1.2.1.2.2.1.2.2": [
                "GigabitEthernet0/1",
                "FastEthernet0/0",
                "eth0",
            ],
            "service": ["10.0.0.1", "10.0.0.2", "192.168.1.1"],
        },
    },
    "coldStart": {
        "payload": {
            "name": "coldStart",
            "description": "coldStart",
            "message": "coldStart",
            "status": "firing",
            "severity": "warning",
            "source": ["snmp"],
            "service": "10.0.0.5",
            "labels": {},
        },
        "parameters": {
            "service": ["10.0.0.5", "10.0.0.6", "172.16.0.1"],
        },
    },
    "authenticationFailure": {
        "payload": {
            "name": "authenticationFailure",
            "description": "authenticationFailure",
            "message": "authenticationFailure",
            "status": "firing",
            "severity": "warning",
            "source": ["snmp"],
            "service": "192.168.1.50",
            "labels": {},
        },
        "parameters": {
            "service": ["192.168.1.50", "10.0.0.3", "172.16.0.10"],
        },
    },
    "linkUp": {
        "payload": {
            "name": "linkUp",
            "description": "1.3.6.1.2.1.2.2.1.2.3 = GigabitEthernet0/2",
            "message": "1.3.6.1.2.1.2.2.1.2.3 = GigabitEthernet0/2",
            "status": "firing",
            "severity": "info",
            "source": ["snmp"],
            "service": "10.0.0.1",
            "labels": {
                "1.3.6.1.2.1.2.2.1.2.3": "GigabitEthernet0/2",
                "1.3.6.1.2.1.2.2.1.7.3": "1",
            },
        },
        "parameters": {
            "labels.1.3.6.1.2.1.2.2.1.2.3": [
                "GigabitEthernet0/2",
                "FastEthernet0/1",
                "eth1",
            ],
            "service": ["10.0.0.1", "10.0.0.2", "192.168.1.1"],
        },
    },
}
