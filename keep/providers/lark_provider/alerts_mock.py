ALERTS = {
    "header": {
        "event_id": "evt_1234567890",
        "event_type": "helpdesk.ticket.created_v1",
        "create_time": "1706000000000",
        "token": "verification_token",
        "app_id": "cli_abcdef123456",
        "tenant_key": "tenant_key_123",
    },
    "event": {
        "ticket": {
            "ticket_id": "ticket_6234567890",
            "helpdesk_id": "helpdesk_001",
            "summary": "Production database connection timeout",
            "description": "Users are experiencing intermittent connection timeouts when accessing the production database. Error rate has increased to 15% in the last 30 minutes.",
            "status": {
                "name": "Open",
                "id": "1",
            },
            "priority": {
                "name": "Urgent",
                "id": "1",
            },
            "created_at": "2025-01-23T10:30:00Z",
            "updated_at": "2025-01-23T10:30:00Z",
            "channel": "helpdesk",
        }
    },
}
