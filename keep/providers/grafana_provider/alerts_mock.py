ALERTS = {
    "HighMemoryConsumption": {
        "service": "api",
        "payload": {
            "condition": "B",
            "data": [
                {
                    "datasourceUid": "datasource2",
                    "model": {
                        "conditions": [
                            {
                                "evaluator": {"params": [80], "type": "gt"},
                                "operator": {"type": "or"},
                                "query": {"params": ["B", "10m", "now"]},
                                "reducer": {"params": [], "type": "avg"},
                                "type": "query",
                            }
                        ],
                        "datasource": {"type": "grafana", "uid": "datasource2"},
                        "expression": "",
                        "hide": False,
                        "intervalMs": 2000,
                        "maxDataPoints": 50,
                        "refId": "B",
                        "type": "classic_conditions",
                    },
                    "queryType": "",
                    "refId": "B",
                    "relativeTimeRange": {"from": 600, "to": 0},
                }
            ],
            "execErrState": "Alerting",
            "folderUID": "keep_alerts",
            "for_": "10m",
            "isPaused": False,
            "labels": {"severity": "warning", "monitor": "memory"},
            "noDataState": "NoData",
            "orgID": 1,
            "ruleGroup": "keep_group_2",
            "title": "High Memory Usage",
            "annotations": {
                "summary": "Memory Usage High on {{ host.name }}",
            },
        },
        "parameters": {
            "labels.monitor": ["server1", "server2", "server3"],
            "for_": ["10m", "30m", "1h"],
        },
        "renders": {
            "host.name": [
                "srv1-us1-prod",
                "srv2-us1-prod",
                "srv1-eu1-prod",
                "srv3-us1-prod",
                "srv2-eu1-prod",
                "srv1-ap1-prod",
                "srv2-ap1-prod",
                "srv1-us2-prod",
            ],
        },
    },
    "NetworkLatencyIsHigh": {
        "service": "db",
        "payload": {
            "condition": "C",
            "data": [
                {
                    "datasourceUid": "datasource3",
                    "model": {
                        "conditions": [
                            {
                                "evaluator": {"params": [100], "type": "gt"},
                                "operator": {"type": "and"},
                                "query": {"params": ["C", "15m", "now"]},
                                "reducer": {"params": [], "type": "max"},
                                "type": "query",
                            }
                        ],
                        "datasource": {"type": "grafana", "uid": "datasource3"},
                        "expression": "",
                        "hide": False,
                        "intervalMs": 3000,
                        "maxDataPoints": 30,
                        "refId": "C",
                        "type": "classic_conditions",
                    },
                    "queryType": "",
                    "refId": "C",
                    "relativeTimeRange": {"from": 900, "to": 0},
                }
            ],
            "execErrState": "Alerting",
            "folderUID": "keep_alerts",
            "for_": "15m",
            "isPaused": False,
            "labels": {"severity": "info", "monitor": "network"},
            "noDataState": "NoData",
            "orgID": 1,
            "ruleGroup": "keep_group_3",
            "title": "Network Latency High",
            "annotations": {
                "summary": "Network Latency High on {{ host.name }}",
            },
        },
        "parameters": {
            "labels.monitor": ["router1", "router2", "router3"],
            "for_": ["15m", "45m", "1h"],
        },
        "renders": {
            "host.name": [
                "srv1-us1-prod",
                "srv2-us1-prod",
                "srv1-eu1-prod",
                "srv3-us1-prod",
                "srv2-eu1-prod",
                "srv1-ap1-prod",
                "srv2-ap1-prod",
                "srv1-us2-prod",
            ],
        },
    },
}
