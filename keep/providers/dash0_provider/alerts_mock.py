ALERTS = {
  "type": "alert.resolved",
  "data": {
    "issue": {
      "id": "b9a9da0b-7a79-4a1d-abf3-5cd07649e80a",
      "issueIdentifier": "6820705469291328438",
      "dataset": "default",
      "start": "2025-02-03T07:17:17.474101621Z",
      "end": "2025-02-03T07:24:17.474101621Z",
      "status": "resolved",
      "summary": "This is a summay",
      "description": "This is a description",
      "labels": [
        {
          "key": "service.name",
          "value": {
            "stringValue": "my-first-observable-service"
          }
        },
        {
          "key": "dash0.resource.name",
          "value": {
            "stringValue": "my-first-observable-service"
          }
        }
      ],
      "annotations": [],
      "checkrules": [
        {
          "id": "97daff98-e694-421d-abda-d53b23ccfd41",
          "version": 1,
          "name": "New Check Rule",
          "expression": "increase({otel_metric_name = \"dash0.logs\"}[5m]) >= $__threshold",
          "thresholds": {
            "degraded": 1,
            "failed": 5
          },
          "interval": "1m0s",
          "for": "0s",
          "keepFiringFor": "0s",
          "summary": "This is a summay",
          "description": "This is a description",
          "labels": {},
          "annotations": {},
          "url": "https://app.dash0.com/alerting/check-rules?org=477cb1f5-90ca-404e-8533-7a1907b58669&s=eJxljU0OwiAUhO_y1sW-0tYKB_AA6sodhYcSsU34WTXcXerKxOXMN19mgxbkBjasb5DAkY8MOcP-hpPsuEQ8IOIdGkjrH-fihxuVVKRUR4asyj5BaaBVnkJyy6PVT9IvFrKnuP9946WmK3nSya3L3jpTdTEZZa04MTqKgQ28M0zNRjEz9jPvtbZm6Oqfi-fsfdSBqLopZCqlfADAkT0J"
        }
      ],
      "url": "https://app.dash0.com/alerting/failed-checks?org=477cb1f5-90ca-404e-8533-7a1907b58669&s=eJxlT71uwyAQfhfmEJ8xNoY36NIuVYduhzlaFMdUgNMh8rsXqg6Vst3p-7-zjpk78ylemWECxMhBcBheQZleGIAzALyzEyvxARf6H-6wYKZSSY487mthx4l1uFIqYfvoPIaVHF8-abnklpiDI4upnSHnnZ5clVqN2iFYrlBpLrF3HK0f-Lg4UJPUNAPWrD8BbSX4QNWDTbMABaOctND9IGY5zK1zuNKLf46NtmAJcXvcIE2vzlLJ341oKyHeKN0CfbcBjkotnt_aW5vGL6oWJe10HMcPHhhbwg%3D%3D"
    }
  }
}