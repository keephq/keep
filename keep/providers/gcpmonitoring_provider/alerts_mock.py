ALERTS = {
    "test-incident": {
        "payload": {
            "version": "test",
            "incident": {
                "incident_id": "12345",
                "scoping_project_id": "12345",
                "scoping_project_number": 12345,
                "url": "http://www.example.com",
                "started_at": 0,
                "ended_at": 0,
                "state": "OPEN",
                "summary": "Test Incident",
                "apigee_url": "http://www.example.com",
                "observed_value": "1.0",
                "resource": {
                    "type": "example_resource",
                    "labels": {"example": "label"},
                },
                "resource_type_display_name": "Example Resource Type",
                "resource_id": "12345",
                "resource_display_name": "Example Resource",
                "resource_name": "projects/12345/example_resources/12345",
                "metric": {
                    "type": "test.googleapis.com/metric",
                    "displayName": "Test Metric",
                    "labels": {"example": "label"},
                },
                "metadata": {
                    "system_labels": {"example": "label"},
                    "user_labels": {"example": "label"},
                },
                "policy_name": "projects/12345/alertPolicies/12345",
                "policy_user_labels": {"example": "label"},
                "documentation": "Test documentation",
                "condition": {
                    "name": "projects/12345/alertPolicies/12345/conditions/12345",
                    "displayName": "Example condition",
                    "conditionThreshold": {
                        "filter": 'metric.type="test.googleapis.com/metric" resource.type="example_resource"',
                        "comparison": "COMPARISON_GT",
                        "thresholdValue": 0.5,
                        "duration": "0s",
                        "trigger": {"count": 1},
                    },
                },
                "condition_name": "Example condition",
                "threshold_value": "0.5",
            },
        },
        "parameters": {},
    },
}
