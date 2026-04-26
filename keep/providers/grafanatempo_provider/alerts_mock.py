from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus

# Simulated Grafana Tempo search API responses (from /api/search)
ALERTS = [
    {
        "traceID": "3c9b8a1f2e4d5678abcd1234efgh5678",
        "rootServiceName": "payment-api",
        "rootTraceName": "POST /v1/payments/charge",
        "startTimeUnixNano": "1731650400000000000",
        "durationMs": 8453,
        "spanSets": [
            {
                "spans": [
                    {
                        "spanID": "abc123def456",
                        "startTimeUnixNano": "1731650400000000000",
                        "durationNanos": "8453000000",
                        "attributes": [
                            {"key": "status", "value": {"stringValue": "error"}},
                            {"key": "http.status_code", "value": {"intValue": "500"}},
                        ],
                    }
                ],
                "matched": 1,
            }
        ],
    },
    {
        "traceID": "9f8e7d6c5b4a3210fedcba0987654321",
        "rootServiceName": "inventory-service",
        "rootTraceName": "GET /api/products/search",
        "startTimeUnixNano": "1731650300000000000",
        "durationMs": 4812,
        "spanSets": [
            {
                "spans": [
                    {
                        "spanID": "xyz789abc123",
                        "startTimeUnixNano": "1731650300000000000",
                        "durationNanos": "4812000000",
                        "attributes": [
                            {"key": "status", "value": {"stringValue": "ok"}},
                            {"key": "db.system", "value": {"stringValue": "postgresql"}},
                        ],
                    }
                ],
                "matched": 1,
            }
        ],
    },
    {
        "traceID": "1a2b3c4d5e6f7890abcdef1234567890",
        "rootServiceName": "order-processor",
        "rootTraceName": "ProcessOrderEvent",
        "startTimeUnixNano": "1731650200000000000",
        "durationMs": 2350,
        "spanSets": [
            {
                "spans": [
                    {
                        "spanID": "def456ghi789",
                        "startTimeUnixNano": "1731650200000000000",
                        "durationNanos": "2350000000",
                        "attributes": [
                            {"key": "status", "value": {"stringValue": "error"}},
                            {"key": "messaging.system", "value": {"stringValue": "kafka"}},
                        ],
                    }
                ],
                "matched": 1,
            }
        ],
    },
]
