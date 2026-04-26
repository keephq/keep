ALERTS = [
    {
        "id": "10001",
        "title": "Unable to process payroll - integration timeout",
        "incomingMessage": "Our payroll integration has been timing out since 09:00 UTC. Affecting ~200 employees.",
        "status": {"refName": "Open"},
        "priority": {"refName": "1 - Critical"},
        "lastModifiedDate": "2024-11-15T09:30:00Z",
    },
    {
        "id": "10002",
        "title": "Inventory sync discrepancy between WH and NetSuite",
        "incomingMessage": "Warehouse counts differ from NetSuite by more than 5% on SKUs 1001-1050.",
        "status": {"refName": "Escalated"},
        "priority": {"refName": "2 - High"},
        "lastModifiedDate": "2024-11-15T08:15:00Z",
    },
    {
        "id": "10003",
        "title": "Sales order PDF rendering issue",
        "incomingMessage": "PDF templates for SO-12345 through SO-12360 display incorrect tax totals.",
        "status": {"refName": "Pending Customer Reply"},
        "priority": {"refName": "3 - Medium"},
        "lastModifiedDate": "2024-11-14T16:45:00Z",
    },
]
