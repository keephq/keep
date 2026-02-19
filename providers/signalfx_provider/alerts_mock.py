ALERTS = {
    "simulate": {
        "payload": {
            "severity": "Critical",
            "statusExtended": "anomalous",
            "detectorUrl": "https://app.signalfx.com/#/detector/XXXX",
            "incidentId": "1234",
            "originatingMetric": "sf.org.log.numMessagesDroppedThrottle",
            "detectOnCondition": "when(A < threshold(1))",
            "messageBody": 'Rule "logs" in detector "logs" cleared at Thu, 29 Feb 2024 11:48:32 GMT.\n\nCurrent signal value for sf.org.log.numMessagesDroppedThrottle: 0\n\nSignal details:\n{sf_metric=sf.org.log.numMessagesDroppedThrottle, orgId=XXXX}',
            "inputs": {
                "A": {
                    "value": "0",
                    "fragment": "data(...A')",
                    "_S2": {"value": "1", "fragment": "threshold(1)"},
                },
                "rule": "logs",
                "description": "The value of sf.org.log.numMessagesDroppedThrottle is below 1.",
                "messageTitle": "Manually resolved: logs (logs)",
                "sf_schema": 2,
                "eventType": "XXXX_XXXX_logs",
                "runbookUrl": None,
                "triggeredWhileMuted": False,
            },
        }
    }
}
