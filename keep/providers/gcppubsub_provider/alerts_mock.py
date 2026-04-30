import base64
import json

# GKE cluster security bulletin notification
_gke_security = {
    "payload": {
        "resourceType": "GKE Security Bulletin",
        "clusterId": "projects/my-project/locations/us-central1/clusters/prod-cluster",
        "typeUrl": "type.googleapis.com/google.container.v1beta1.SecurityBulletinEvent",
        "resourceVersion": "1.28.5-gke.1000",
        "cveIds": ["CVE-2024-1234"],
        "severity": "CRITICAL",
    }
}

# GKE end-of-support notification
_gke_eos = {
    "payload": {
        "resourceType": "GKE End of Life Notification",
        "clusterId": "projects/my-project/locations/us-central1/clusters/staging-cluster",
        "typeUrl": "type.googleapis.com/google.container.v1beta1.UpgradeAvailableEvent",
        "currentVersion": "1.26.12-gke.1000",
        "targetVersion": "1.27.8-gke.1000",
    }
}

# Generic application event
_app_event = {
    "service": "payment-api",
    "environment": "production",
    "event": "high_error_rate",
    "error_rate_pct": 12.5,
    "status": "FIRING",
    "threshold_pct": 5.0,
}

ALERTS = [
    {
        "message": {
            "messageId": "msg-001-security",
            "publishTime": "2024-11-15T10:00:00Z",
            "data": base64.b64encode(json.dumps(_gke_security).encode()).decode(),
            "attributes": {"notificationType": "SecurityBulletinEvent", "clusterName": "prod-cluster"},
        },
        "ackId": "ack-001",
    },
    {
        "message": {
            "messageId": "msg-002-eos",
            "publishTime": "2024-11-15T09:00:00Z",
            "data": base64.b64encode(json.dumps(_gke_eos).encode()).decode(),
            "attributes": {"notificationType": "EndOfSupportEvent", "clusterName": "staging-cluster"},
        },
        "ackId": "ack-002",
    },
    {
        "message": {
            "messageId": "msg-003-app",
            "publishTime": "2024-11-15T08:30:00Z",
            "data": base64.b64encode(json.dumps(_app_event).encode()).decode(),
            "attributes": {"notificationType": "ApplicationAlert", "service": "payment-api"},
        },
        "ackId": "ack-003",
    },
]
