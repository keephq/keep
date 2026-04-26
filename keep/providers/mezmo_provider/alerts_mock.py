ALERTS = [
    {
        "alert_id": "mezmo-alert-001",
        "name": "High error rate on payment-service",
        "description": "More than 50 ERROR logs matched in the last 5 minutes.",
        "level": "error",
        "timestamp": "2024-01-15T14:30:00Z",
        "query": "level:error app:payment-service",
        "url": "https://app.mezmo.com/org/views/abc123",
        "app": "payment-service",
        "host": "prod-payments-01",
        "account": "acme-corp",
        "lines": [
            {
                "timestamp": "2024-01-15T14:29:55Z",
                "app": "payment-service",
                "level": "error",
                "line": "NullPointerException in PaymentProcessor.charge() line 87",
            },
            {
                "timestamp": "2024-01-15T14:29:50Z",
                "app": "payment-service",
                "level": "error",
                "line": "Failed to connect to payment gateway: timeout after 30s",
            },
        ],
    },
    {
        "alert_id": "mezmo-alert-002",
        "name": "Critical: database connection pool exhausted",
        "level": "critical",
        "timestamp": 1705327800000,
        "query": "connection pool exhausted",
        "url": "https://app.mezmo.com/org/views/def456",
        "app": "api-server",
        "host": "prod-api-03",
        "account": "acme-corp",
        "lines": [
            {
                "timestamp": 1705327795000,
                "app": "api-server",
                "level": "critical",
                "line": "HikariPool: Connection pool exhausted. Max pool size: 50",
            }
        ],
    },
    {
        "alert_id": "mezmo-alert-003",
        "name": "Unusual login attempts detected",
        "description": "Warning-level auth events exceeded threshold of 100 in 10 minutes.",
        "level": "warning",
        "timestamp": "2024-01-15T13:00:00Z",
        "query": "app:auth-service level:warn login failed",
        "url": "https://app.mezmo.com/org/views/ghi789",
        "app": "auth-service",
        "host": "prod-auth-01",
        "account": "acme-corp",
    },
]
