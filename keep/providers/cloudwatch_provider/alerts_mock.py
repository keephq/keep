ALERTS = {
    "high_cpu_usage": {
        "payload": {
            "Message": {
                "AlarmName": "HighCPUUsage",
                "MetricName": "CPUUtilization",
                "Namespace": "AWS/EC2",
                "Threshold": 90,
                "ComparisonOperator": "GreaterThanOrEqualToThreshold",
                "Priority": "P3",
            }
        },
        "parameters": {
            "Message.AlarmName": ["HighCPUUsage", "HighCPUUsageOnAPod", "PodRecycled"],
            "Message.Application": ["mailing-app", "producers", "main-app", "core"],
            "Message.Threshold": [90, 80, 70, 95],
        },
    },
}
