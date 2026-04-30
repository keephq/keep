ALERTS = {
  "data": {
    "id": "12345",
    "type": "incident",
    "attributes": {
      "name": "Production API",
      "url": "https://api.example.com",
      "cause": "down",
      "status": "started",
      "started_at": "2024-03-15T10:30:00.000Z",
      "resolved_at": None,
      "monitor_summary": "Production API is not responding",
      "monitor_url": "https://api.example.com/health",
      "team_name": "acme"
    },
    "relationships": {
      "monitor": {
        "data": {
          "id": "98765",
          "type": "monitor"
        }
      }
    }
  }
}
