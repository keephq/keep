ALERTS = {
  "event_type": "monitor.failure",
  "happened_at": "2024-03-15T10:30:00.000Z",
  "message": "daily-report-job failed to complete within the expected time",
  "environment": "production",
  "monitor": {
    "key": "daily-report-job",
    "name": "Daily Report Job",
    "type": "job",
    "schedule": "0 9 * * *",
    "status": "failing",
    "passing": False,
    "running": False,
    "url": "https://cronitor.io/monitors/daily-report-job"
  },
  "series": "a1b2c3d4"
}
