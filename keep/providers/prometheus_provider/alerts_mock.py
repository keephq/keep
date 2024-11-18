ALERTS = {
    "high_cpu_usage": {
        "payload": {
            "summary": "CPU usage is over 90%",
            "labels": {
                "instance": "example1",
                "job": "example2",
                "workload": "somecoolworkload",
                "severity": "critical",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.service": ["calendar-producer-java-otel-api-dd", "kafka", "api", "queue", "db"],
            "labels.instance": ["instance1", "instance2", "instance3"],
        },
    },
    "mq_third_full": {
        "payload": {
            "summary": "Message queue is over 33% capacity",
            "labels": {
                "severity": "warning",
                "customer_id": "acme"
            },
        },
        "parameters": {
            "labels.queue": ["queue1", "queue2", "queue3"],
            "labels.service": ["calendar-producer-java-otel-api-dd", "kafka", "queue"],
            "labels.mq_manager": ["mq_manager1", "mq_manager2", "mq_manager3"],
        },
    },
    "disk_space_low": {
        "payload": {
            "summary": "Disk space is below 20%",
            "labels": {
                "severity": "warning",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.service": ["calendar-producer-java-otel-api-dd", "kafka", "api", "queue", "db"],
            "labels.instance": ["instance1", "instance2", "instance3"],
        },
    },
    "network_latency_high": {
        "payload": {
            "summary": "Network latency is higher than normal",
            "labels": {
                "severity": "info",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.service": ["calendar-producer-java-otel-api-dd", "kafka", "api", "queue", "db"],
            "labels.instance": ["instance1", "instance2", "instance3"],
        },
    },
}
