"""Mock alert data for SolarWinds provider testing."""

# Mock active alert (from Orion.AlertActive)
ACTIVE_ALERT = {
    "AlertActiveID": "12345",
    "AlertObjectID": "42",
    "AlertID": "1001",
    "Name": "High CPU Usage",
    "Message": "CPU utilization on core-router exceeded 90% threshold.",
    "Severity": 3,
    "ObjectType": "Node",
    "TriggeredDateTime": "2024-11-15T10:23:00Z",
    "Acknowledged": False,
    "AcknowledgedDateTime": None,
    "AcknowledgedBy": None,
    "RelatedNodeCaption": "core-router-01",
}

# Mock acknowledged alert
ACKNOWLEDGED_ALERT = {
    "AlertActiveID": "12346",
    "AlertObjectID": "43",
    "AlertID": "1002",
    "Name": "Interface Down",
    "Message": "GigabitEthernet0/1 on core-switch-01 is operationally down.",
    "Severity": 3,
    "ObjectType": "Node",
    "TriggeredDateTime": "2024-11-15T09:00:00Z",
    "Acknowledged": True,
    "AcknowledgedDateTime": "2024-11-15T09:15:00Z",
    "AcknowledgedBy": "admin",
    "RelatedNodeCaption": "core-switch-01",
}

# Mock warning alert
WARNING_ALERT = {
    "AlertActiveID": "12347",
    "AlertObjectID": "44",
    "AlertID": "1003",
    "Name": "High Memory Usage",
    "Message": "Memory utilization on app-server-02 exceeded 80% threshold.",
    "Severity": 2,
    "ObjectType": "Node",
    "TriggeredDateTime": "2024-11-15T11:00:00Z",
    "Acknowledged": False,
    "AcknowledgedDateTime": None,
    "AcknowledgedBy": None,
    "RelatedNodeCaption": "app-server-02",
}

# Mock active alerts list (response from Orion.AlertActive query)
ACTIVE_ALERTS = [ACTIVE_ALERT, ACKNOWLEDGED_ALERT, WARNING_ALERT]

# Mock down node (from Orion.Nodes where Status != 1)
DOWN_NODE = {
    "NodeID": "101",
    "Caption": "branch-router-02",
    "IPAddress": "192.168.10.1",
    "Status": 2,
    "StatusDescription": "Down",
    "LastBoot": "2024-11-10T08:00:00Z",
    "MachineType": "Cisco IOS",
    "Vendor": "Cisco",
}

# Mock warning node
WARNING_NODE = {
    "NodeID": "102",
    "Caption": "access-switch-03",
    "IPAddress": "10.0.1.5",
    "Status": 3,
    "StatusDescription": "Warning",
    "LastBoot": "2024-11-01T06:00:00Z",
    "MachineType": "Juniper Junos",
    "Vendor": "Juniper",
}

# Mock nodes list (response from Orion.Nodes query)
DOWN_NODES = [DOWN_NODE, WARNING_NODE]

# SWIS query response structure
ALERTS_QUERY_RESPONSE = {
    "results": ACTIVE_ALERTS,
}

NODES_QUERY_RESPONSE = {
    "results": DOWN_NODES,
}
