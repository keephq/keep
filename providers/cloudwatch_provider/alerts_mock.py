ALERTS = {
    "high_cpu_usage": {
        "payload": {
            "Message": {
                "AlarmName": "HighCPUUsage",
                "AlarmDescription": "CPU utilization is above 90% threshold",
                "MetricName": "CPUUtilization",
                "Namespace": "AWS/EC2",
                "Threshold": 90,
                "ComparisonOperator": "GreaterThanOrEqualToThreshold",
                "Priority": "P3",
            }
        },
        "parameters": {
            "Message.AlarmName": ["HighCPUUsage", "HighCPUUsageOnAPod", "PodRecycled"],
            "Message.AlarmDescription": [
                "CPU utilization is above threshold",
                "Pod CPU usage exceeds safe limits",
                "Pod was recycled due to resource constraints",
            ],
            "Message.Application": ["mailing-app", "producers", "main-app", "core"],
            "Message.Threshold": [90, 80, 70, 95],
        },
    },
    "high_memory_usage": {
        "payload": {
            "Message": {
                "AlarmName": "HighMemoryUsage",
                "AlarmDescription": "Memory utilization is above 85% threshold",
                "MetricName": "MemoryUtilization",
                "Namespace": "AWS/ECS",
                "Threshold": 85,
                "ComparisonOperator": "GreaterThanOrEqualToThreshold",
                "Priority": "P2",
            }
        },
        "parameters": {
            "Message.AlarmName": [
                "HighMemoryUsage",
                "ContainerMemoryHigh",
                "ServiceMemoryAlert",
            ],
            "Message.AlarmDescription": [
                "Memory utilization exceeded threshold",
                "Container using excessive memory",
                "Service memory usage is critical",
            ],
            "Message.Application": ["api-service", "cache-service", "worker-service"],
            "Message.Threshold": [85, 75, 90],
        },
    },
    "high_error_rate": {
        "payload": {
            "Message": {
                "AlarmName": "APIErrorRate",
                "AlarmDescription": "API error rate exceeds 5% threshold",
                "MetricName": "5XXError",
                "Namespace": "AWS/ApiGateway",
                "Threshold": 5,
                "ComparisonOperator": "GreaterThanThreshold",
                "Priority": "P1",
            }
        },
        "parameters": {
            "Message.AlarmName": ["APIErrorRate", "ServiceErrors", "EndpointFailures"],
            "Message.AlarmDescription": [
                "API error rate above normal levels",
                "Service experiencing high error count",
                "Critical endpoint failure detected",
            ],
            "Message.Application": ["payment-api", "user-service", "order-system"],
            "Message.Threshold": [5, 3, 1],
        },
    },
}
