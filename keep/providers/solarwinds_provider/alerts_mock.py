"""Mock SWIS query results for unit-testing the SolarWinds provider mapping."""

ALERTS = {
    "node_critical": {
        "results": [
            {
                "AlertActiveID": 12001,
                "AlertObjectID": 4501,
                "AlertID": 87,
                "TriggeredDateTime": "2026-03-15T14:23:42Z",
                "TriggeredMessage": "Node web-prod-01 is down (no response to ICMP).",
                "Acknowledged": False,
                "AcknowledgedBy": None,
                "AcknowledgedDateTime": None,
                "EntityCaption": "web-prod-01",
                "EntityType": "Orion.Nodes",
                "RelatedNodeCaption": "web-prod-01",
                "AlertName": "Node down",
                "Severity": 4,
                "Description": "Triggered when a node fails to respond to polling.",
            }
        ]
    },
    "interface_warning": {
        "results": [
            {
                "AlertActiveID": 12002,
                "AlertObjectID": 4502,
                "AlertID": 91,
                "TriggeredDateTime": "2026-03-15T14:25:12Z",
                "TriggeredMessage": "Interface Gi0/1 utilization above 80%.",
                "Acknowledged": False,
                "EntityCaption": "Gi0/1 - core-sw-01",
                "EntityType": "Orion.NPM.Interfaces",
                "RelatedNodeCaption": "core-sw-01",
                "AlertName": "Interface high utilization",
                "Severity": 2,
            }
        ]
    },
    "acknowledged_volume": {
        "results": [
            {
                "AlertActiveID": 12003,
                "AlertObjectID": 4503,
                "AlertID": 102,
                "TriggeredDateTime": "2026-03-15T13:00:00Z",
                "TriggeredMessage": "Volume /var on db-prod-02 above 90% capacity.",
                "Acknowledged": True,
                "AcknowledgedBy": "oncall",
                "AcknowledgedDateTime": "2026-03-15T13:42:18Z",
                "EntityCaption": "/var",
                "EntityType": "Orion.Volumes",
                "RelatedNodeCaption": "db-prod-02",
                "AlertName": "Volume nearly full",
                "Severity": 3,
            }
        ]
    },
    "informational": {
        "results": [
            {
                "AlertActiveID": 12004,
                "AlertObjectID": 4504,
                "AlertID": 30,
                "TriggeredDateTime": "2026-03-15T14:30:00Z",
                "TriggeredMessage": "New device discovered: printer-3rd-floor.",
                "Acknowledged": False,
                "EntityCaption": "printer-3rd-floor",
                "EntityType": "Orion.Nodes",
                "RelatedNodeCaption": "printer-3rd-floor",
                "AlertName": "New device discovered",
                "Severity": 0,
            }
        ]
    },
}
