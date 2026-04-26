ALERTS = [
    {
        "check": {
            "id": "check-001",
            "name": "No Critical Vulnerabilities",
            "category": "security",
        },
        "service": {
            "id": "svc-payment",
            "name": "Payment Service",
            "htmlUrl": "https://app.opslevel.com/services/payment-service",
        },
        "result": "failed",
        "message": "Check 'No Critical Vulnerabilities' failed for service Payment Service — 3 critical CVEs detected in dependencies.",
    },
    {
        "check": {
            "id": "check-002",
            "name": "Has On-Call Rotation",
            "category": "reliability",
        },
        "service": {
            "id": "svc-auth",
            "name": "Auth Service",
            "htmlUrl": "https://app.opslevel.com/services/auth-service",
        },
        "result": "failed",
        "message": "Check 'Has On-Call Rotation' failed for service Auth Service — no on-call rotation configured.",
    },
    {
        "check": {
            "id": "check-003",
            "name": "Has Runbook",
            "category": "quality",
        },
        "service": {
            "id": "svc-notification",
            "name": "Notification Service",
            "htmlUrl": "https://app.opslevel.com/services/notification-service",
        },
        "result": "passed",
        "message": "Check 'Has Runbook' passed for service Notification Service.",
    },
]
