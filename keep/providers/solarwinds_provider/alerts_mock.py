ALERTS = {
    "NodeDown": {
        "payload": {
            "AlertActiveID": "1001",
            "AlertName": "Node Down",
            "AlertDescription": "A node in the network is not responding",
            "AlertMessage": "Node {{NodeName}} is down",
            "Severity": 2,
            "Acknowledged": False,
            "TriggeredDateTime": "2024-01-01T00:00:00Z",
            "EntityType": "Orion.Nodes",
            "ObjectType": "Node",
        },
        "parameters": {
            "NodeName": [
                "web-server-01",
                "db-server-02",
                "app-server-03",
                "cache-server-01",
            ],
            "AlertActiveID": ["1001", "1002", "1003", "1004"],
        },
    },
    "HighCPUUtilization": {
        "payload": {
            "AlertActiveID": "2001",
            "AlertName": "High CPU Utilization",
            "AlertDescription": "CPU utilization has exceeded threshold",
            "AlertMessage": "CPU on {{NodeName}} is above 95%",
            "Severity": 1,
            "Acknowledged": False,
            "TriggeredDateTime": "2024-01-01T00:00:00Z",
            "EntityType": "Orion.Nodes",
            "ObjectType": "Node",
        },
        "parameters": {
            "NodeName": [
                "web-server-01",
                "db-server-02",
                "app-server-03",
            ],
            "AlertActiveID": ["2001", "2002", "2003"],
        },
    },
    "InterfaceDown": {
        "payload": {
            "AlertActiveID": "3001",
            "AlertName": "Interface Down",
            "AlertDescription": "A network interface is down",
            "AlertMessage": "Interface {{InterfaceName}} on {{NodeName}} is down",
            "Severity": 2,
            "Acknowledged": False,
            "TriggeredDateTime": "2024-01-01T00:00:00Z",
            "EntityType": "Orion.NPM.Interfaces",
            "ObjectType": "Interface",
        },
        "parameters": {
            "NodeName": [
                "switch-core-01",
                "router-edge-01",
                "firewall-01",
            ],
            "InterfaceName": ["GigabitEthernet0/1", "FastEthernet0/0", "eth0"],
            "AlertActiveID": ["3001", "3002", "3003"],
        },
    },
    "VolumeSpaceLow": {
        "payload": {
            "AlertActiveID": "4001",
            "AlertName": "Volume Space Running Low",
            "AlertDescription": "Disk volume is running low on free space",
            "AlertMessage": "Volume {{VolumeName}} on {{NodeName}} is above 90% capacity",
            "Severity": 1,
            "Acknowledged": False,
            "TriggeredDateTime": "2024-01-01T00:00:00Z",
            "EntityType": "Orion.Volumes",
            "ObjectType": "Volume",
        },
        "parameters": {
            "NodeName": [
                "file-server-01",
                "db-server-02",
                "app-server-03",
            ],
            "VolumeName": ["C:", "/dev/sda1", "/var/log"],
            "AlertActiveID": ["4001", "4002", "4003"],
        },
    },
    "HighMemoryUtilization": {
        "payload": {
            "AlertActiveID": "5001",
            "AlertName": "High Memory Utilization",
            "AlertDescription": "Memory utilization has exceeded threshold",
            "AlertMessage": "Memory on {{NodeName}} is above 95%",
            "Severity": 1,
            "Acknowledged": False,
            "TriggeredDateTime": "2024-01-01T00:00:00Z",
            "EntityType": "Orion.Nodes",
            "ObjectType": "Node",
        },
        "parameters": {
            "NodeName": [
                "web-server-01",
                "db-server-02",
                "cache-server-01",
            ],
            "AlertActiveID": ["5001", "5002", "5003"],
        },
    },
}
