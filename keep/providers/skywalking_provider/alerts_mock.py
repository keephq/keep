"""Mock alert payloads for the Apache SkyWalking provider."""

ALERTS = {
    "ServiceHighResponseTime": {
        "payload": {
            "alarms": [
                {
                    "scope": "Service",
                    "name": "payment-service",
                    "id0": "cGF5bWVudC1zZXJ2aWNl.1",
                    "id1": "",
                    "ruleName": "service_resp_time_rule",
                    "alarmMessage": "Response time of service payment-service is more than 1000ms in 3 minutes of last 10 minutes",
                    "startTime": 1743200000000,
                    "tags": [
                        {"key": "level", "value": "WARNING"},
                        {"key": "service", "value": "payment-service"},
                    ],
                    "events": [],
                }
            ]
        },
        "parameters": {
            "alarms.0.name": [
                "payment-service",
                "order-service",
                "inventory-service",
                "user-service",
            ],
        },
    },
    "ServiceInstanceJVMHeapHigh": {
        "payload": {
            "alarms": [
                {
                    "scope": "ServiceInstance",
                    "name": "payment-service#10.0.0.1-pid:1234@payment-server",
                    "id0": "cGF5bWVudC1zZXJ2aWNl.1_10.0.0.1-pid:1234@payment-server",
                    "id1": "",
                    "ruleName": "service_instance_jvm_old_gc_time_rule",
                    "alarmMessage": "JVM old GC time of service instance is more than 300ms in 1 minutes of last 10 minutes",
                    "startTime": 1743200100000,
                    "tags": [
                        {"key": "level", "value": "CRITICAL"},
                        {"key": "service", "value": "payment-service"},
                    ],
                    "events": [],
                }
            ]
        },
        "parameters": {
            "alarms.0.name": [
                "payment-service#10.0.0.1-pid:1234@payment-server",
                "order-service#10.0.0.2-pid:5678@order-server",
            ],
        },
    },
    "EndpointHighErrorRate": {
        "payload": {
            "alarms": [
                {
                    "scope": "Endpoint",
                    "name": "POST:/api/v1/payment in payment-service",
                    "id0": "cGF5bWVudC1zZXJ2aWNl.1_UE9TVDovYXBpL3YxL3BheW1lbnQ=",
                    "id1": "",
                    "ruleName": "endpoint_relation_resp_time_rule",
                    "alarmMessage": "Response time of endpoint relation POST:/api/v1/payment in payment-service is more than 1000ms in 1 minutes of last 10 minutes",
                    "startTime": 1743200200000,
                    "tags": [
                        {"key": "level", "value": "ERROR"},
                        {"key": "endpoint", "value": "POST:/api/v1/payment"},
                    ],
                    "events": [],
                }
            ]
        },
        "parameters": {
            "alarms.0.name": [
                "POST:/api/v1/payment in payment-service",
                "GET:/api/v1/orders in order-service",
            ],
        },
    },
    "ServiceSuccessRateLow": {
        "payload": {
            "alarms": [
                {
                    "scope": "Service",
                    "name": "checkout-service",
                    "id0": "Y2hlY2tvdXQtc2VydmljZQ==.1",
                    "id1": "",
                    "ruleName": "service_sla_rule",
                    "alarmMessage": "Successful rate of service checkout-service is lower than 80% in 2 minutes of last 10 minutes",
                    "startTime": 1743200300000,
                    "tags": [
                        {"key": "level", "value": "CRITICAL"},
                        {"key": "service", "value": "checkout-service"},
                    ],
                    "events": [],
                }
            ]
        },
        "parameters": {
            "alarms.0.name": [
                "checkout-service",
                "auth-service",
                "notification-service",
            ],
        },
    },
}
