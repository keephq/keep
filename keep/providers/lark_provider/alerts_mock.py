ALERTS = [
    {
        "schema": "2.0",
        "header": {
            "event_id": "evt-ticket-001",
            "event_type": "helpdesk.ticket.created_v1",
            "create_time": "1714100000000",
            "token": "mock-token",
            "app_id": "cli_mock123",
            "tenant_key": "tenant_mock",
        },
        "event": {
            "ticket": {
                "ticket_id": "TKT-001",
                "name": "Production database connection pool exhausted",
                "description": "All connection slots are full. Services unable to reach the database.",
                "status": "1",
                "urgency": "1",
                "created_at": "1714100000",
                "agent_user_id": "usr_abc123",
            }
        },
    },
    {
        "schema": "2.0",
        "header": {
            "event_id": "evt-ticket-002",
            "event_type": "helpdesk.ticket.updated_v1",
            "create_time": "1714110000000",
            "token": "mock-token",
            "app_id": "cli_mock123",
            "tenant_key": "tenant_mock",
        },
        "event": {
            "ticket": {
                "ticket_id": "TKT-002",
                "name": "API gateway latency spike on /checkout endpoint",
                "description": "P99 latency increased from 200ms to 4000ms. Possible timeout in upstream payment service.",
                "status": "2",
                "urgency": "2",
                "created_at": "1714110000",
                "agent_user_id": "usr_def456",
            }
        },
    },
    {
        "schema": "2.0",
        "header": {
            "event_id": "evt-ticket-003",
            "event_type": "helpdesk.ticket.updated_v1",
            "create_time": "1714120000000",
            "token": "mock-token",
            "app_id": "cli_mock123",
            "tenant_key": "tenant_mock",
        },
        "event": {
            "ticket": {
                "ticket_id": "TKT-003",
                "name": "Disk usage above 85% on logging server",
                "description": "The logging aggregation server has exceeded 85% disk capacity. Log rotation may need adjustment.",
                "status": "3",
                "urgency": "3",
                "created_at": "1714120000",
                "agent_user_id": "usr_ghi789",
            }
        },
    },
]
