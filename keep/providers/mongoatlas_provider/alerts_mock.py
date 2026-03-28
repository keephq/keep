"""
Mock alert payloads for the MongoDB Atlas provider.

These represent typical Atlas alert payloads as returned by the
Atlas Alerts API v2 or delivered via webhook notifications.

References:
  - https://www.mongodb.com/docs/atlas/alert-basics/
  - https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Alerts
"""

ALERTS = {
    "HOST_DOWN": {
        "payload": {
            "id": "5f5a4a5e3b9a1a0001f3a1a1",
            "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
            "eventTypeName": "HOST_DOWN",
            "status": "OPEN",
            "severity": "CRITICAL",
            "humanReadable": "We could not reach your MongoDB process at host1:27017.",
            "hostnameAndPort": "host1:27017",
            "clusterName": "MyCluster",
            "replicaSetName": "rs0",
            "created": "2024-01-15T10:00:00Z",
            "updated": "2024-01-15T10:00:00Z",
        },
        "parameters": {
            "hostnameAndPort": [
                "host1:27017",
                "host2:27017",
                "primary:27017",
            ],
            "clusterName": ["MyCluster", "ProductionDB", "AnalyticsDB"],
        },
    },
    "NO_PRIMARY": {
        "payload": {
            "id": "5f5a4a5e3b9a1a0001f3a1a2",
            "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
            "eventTypeName": "NO_PRIMARY",
            "status": "OPEN",
            "severity": "CRITICAL",
            "humanReadable": "Your replica set has no primary. Read/write operations will fail.",
            "clusterName": "MyCluster",
            "replicaSetName": "rs0",
            "created": "2024-01-15T11:00:00Z",
            "updated": "2024-01-15T11:00:00Z",
        },
        "parameters": {
            "replicaSetName": ["rs0", "rs1", "config-rs"],
            "clusterName": ["MyCluster", "ProductionDB"],
        },
    },
    "REPLICATION_OPLOG_WINDOW_RUNNING_OUT": {
        "payload": {
            "id": "5f5a4a5e3b9a1a0001f3a1a3",
            "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
            "eventTypeName": "REPLICATION_OPLOG_WINDOW_RUNNING_OUT",
            "status": "OPEN",
            "severity": "HIGH",
            "humanReadable": "The oplog window is below the threshold of 1 hour.",
            "clusterName": "MyCluster",
            "replicaSetName": "rs0",
            "metricName": "OPLOG_REPLICATION_LAG_TIME",
            "currentValue": {"number": 45.0, "units": "MINUTES"},
            "created": "2024-01-15T12:00:00Z",
            "updated": "2024-01-15T12:00:00Z",
        },
        "parameters": {
            "clusterName": ["MyCluster", "ProductionDB"],
            "currentValue.number": [30.0, 45.0, 55.0],
        },
    },
    "DISK_FULL": {
        "payload": {
            "id": "5f5a4a5e3b9a1a0001f3a1a4",
            "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
            "eventTypeName": "DISK_FULL",
            "status": "OPEN",
            "severity": "WARNING",
            "humanReadable": "Disk usage on host1:27017 is at 85% capacity.",
            "hostnameAndPort": "host1:27017",
            "clusterName": "MyCluster",
            "metricName": "DISK_PARTITION_SPACE_PERCENT_FREE",
            "currentValue": {"number": 15.0, "units": "RAW_SCALAR"},
            "created": "2024-01-15T13:00:00Z",
            "updated": "2024-01-15T13:00:00Z",
        },
        "parameters": {
            "hostnameAndPort": ["host1:27017", "host2:27017"],
            "currentValue.number": [10.0, 15.0, 20.0],
        },
    },
    "HIGH_QUERY_LATENCY": {
        "payload": {
            "id": "5f5a4a5e3b9a1a0001f3a1a5",
            "groupId": "5f5a4a5e3b9a1a0001f3a1b2",
            "eventTypeName": "QUERY_EXECUTION_TIME_ALERT",
            "status": "OPEN",
            "severity": "WARNING",
            "humanReadable": "Average query execution time is above 100ms threshold.",
            "clusterName": "MyCluster",
            "metricName": "QUERY_TARGETING_SCANNED_OBJECTS_PER_RETURNED",
            "currentValue": {"number": 1250.5, "units": "MILLISECONDS"},
            "created": "2024-01-15T14:00:00Z",
            "updated": "2024-01-15T14:00:00Z",
        },
        "parameters": {
            "clusterName": ["MyCluster", "ProductionDB", "AnalyticsDB"],
            "currentValue.number": [100.0, 250.5, 500.0, 1250.5],
        },
    },
}
