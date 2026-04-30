"""
Mock OpenSupports ticket payloads for testing.
These represent ticket objects returned by the OpenSupports REST API.
Reference: https://www.opensupports.com/support/article/23/how-to-use-the-api/
"""

ALERTS = {
    "HighPriorityTicket": {
        "payload": {
            "id": 42,
            "ticketNumber": "SHD-00042",
            "title": "Production database unreachable",
            "content": "The primary PostgreSQL instance on db-01 is unreachable. Alert triggered by Keep (Prometheus: TargetDown). Please investigate immediately.",
            "priority": 2,
            "closed": 0,
            "date": "2024-01-15 10:30:00",
            "language": "en",
            "owner": {"name": "Alice Smith", "email": "alice@example.com"},
            "department": {"id": 1, "name": "Operations"},
        }
    },
    "MediumPriorityTicket": {
        "payload": {
            "id": 43,
            "ticketNumber": "SHD-00043",
            "title": "High memory usage on app-server-03",
            "content": "Memory usage has exceeded 85% on app-server-03 for more than 10 minutes. Source: Keep (Grafana alert).",
            "priority": 1,
            "closed": 0,
            "date": "2024-01-15 11:00:00",
            "language": "en",
            "owner": None,
            "department": {"id": 2, "name": "Infrastructure"},
        }
    },
    "ClosedTicket": {
        "payload": {
            "id": 41,
            "ticketNumber": "SHD-00041",
            "title": "SSL certificate expiring on api.example.com",
            "content": "SSL certificate was renewed successfully. Ticket resolved.",
            "priority": 1,
            "closed": 1,
            "date": "2024-01-14 09:00:00",
            "language": "en",
            "owner": {"name": "Bob Jones", "email": "bob@example.com"},
            "department": {"id": 1, "name": "Operations"},
        }
    },
}
