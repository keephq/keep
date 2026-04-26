ALERTS = [
    {
        "event": "incident_created",
        "incident": {
            "id": "01HFGH1234567890ABCDEFGHIJ",
            "name": "API Gateway returning 5xx errors",
            "description": "Multiple services are reporting 5xx responses from the API Gateway. Customer impact detected.",
            "severity": "SEV2",
            "current_milestone": "started",
            "started_at": "2024-01-15T10:30:00Z",
            "services": [{"name": "API Gateway"}, {"name": "User Service"}],
            "teams": [{"name": "Platform Engineering"}],
            "tags": [{"name": "production"}, {"name": "api"}],
        },
    },
    {
        "event": "milestone_updated",
        "incident": {
            "id": "01HFGH0987654321ZYXWVUTSRQ",
            "name": "Database connection pool exhausted",
            "description": "Primary database connection pool is exhausted. Write operations failing.",
            "severity": "SEV1",
            "current_milestone": "investigating",
            "started_at": "2024-01-15T09:00:00Z",
            "services": [{"name": "Database"}, {"name": "Order Service"}],
            "teams": [{"name": "Infrastructure"}, {"name": "Backend"}],
            "tags": [{"name": "database"}, {"name": "critical"}],
        },
    },
    {
        "event": "incident_resolved",
        "incident": {
            "id": "01HFGH1111222233334444BBBB",
            "name": "CDN cache invalidation failure",
            "description": "CDN was serving stale assets after deployment. Cache invalidation scripts were failing.",
            "severity": "SEV3",
            "current_milestone": "resolved",
            "started_at": "2024-01-14T15:00:00Z",
            "services": [{"name": "CDN"}, {"name": "Web Frontend"}],
            "teams": [{"name": "DevOps"}],
            "tags": [{"name": "cdn"}, {"name": "deployment"}],
        },
    },
]
