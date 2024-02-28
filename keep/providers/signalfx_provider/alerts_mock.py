ALERTS = {
    "high_cpu_usage": {
        "payload": {
            "summary": "CPU usage is over 90%",
            "labels": {
                "instance": "example1",
                "job": "example2",
                "workfload": "somecoolworkload",
                "severity": "critical",
            },
        },
        "parameters": {
            "labels.host": ["host1", "host2", "host3"],
            "labels.instance": ["instance1", "instance2", "instance3"],
        },
    }
}
