ALERTS = [
    {
        "action": "triggered",
        "data": {
            "id": "01HXYZ123ABC",
            "type": "incidents",
            "attributes": {
                "title": "Database connection pool exhausted in production",
                "slug": "01HXYZ123ABC",
                "status": "triggered",
                "severity": {"name": "critical"},
                "summary": "The primary database connection pool has been exhausted, causing 503 errors across all API endpoints.",
                "created_at": "2024-03-15T10:23:00Z",
                "updated_at": "2024-03-15T10:23:00Z",
                "environment": {"data": {"attributes": {"name": "production"}}},
                "service": {"data": {"attributes": {"name": "api-gateway"}}},
            },
        },
    },
    {
        "action": "acknowledged",
        "data": {
            "id": "01HXYZ456DEF",
            "type": "incidents",
            "attributes": {
                "title": "High memory utilization on web servers",
                "slug": "01HXYZ456DEF",
                "status": "acknowledged",
                "severity": {"name": "high"},
                "summary": "Web server cluster showing sustained memory usage above 90%, potential OOM risk.",
                "created_at": "2024-03-14T08:15:00Z",
                "updated_at": "2024-03-14T08:42:00Z",
                "environment": {"data": {"attributes": {"name": "production"}}},
                "service": {"data": {"attributes": {"name": "web-frontend"}}},
            },
        },
    },
    {
        "action": "resolved",
        "data": {
            "id": "01HXYZ789GHI",
            "type": "incidents",
            "attributes": {
                "title": "Elevated error rate on payment service",
                "slug": "01HXYZ789GHI",
                "status": "resolved",
                "severity": {"name": "medium"},
                "summary": "Payment service returning 5xx errors at elevated rate. Root cause: third-party gateway timeout.",
                "created_at": "2024-03-13T14:00:00Z",
                "updated_at": "2024-03-13T15:30:00Z",
                "environment": {"data": {"attributes": {"name": "production"}}},
                "service": {"data": {"attributes": {"name": "payments"}}},
            },
        },
    },
]
