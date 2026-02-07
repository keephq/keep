ALERTS = {
    \"SkyWalkingAlarm\": {
        \"payload\": {
            \"message\": \"Service response time is too high\",
            \"scope\": \"Service\",
            \"tags\": [
                {\"key\": \"severity\", \"value\": \"CRITICAL\"},
                {\"key\": \"service\", \"value\": \"order-service\"}
            ],
        },
        \"parameters\": {
            \"scope\": [\"Service\", \"ServiceInstance\", \"Endpoint\", \"Process\"],
            \"message\": [
                \"CPU usage is high\",
                \"Memory leak detected\",
                \"Database connection timeout\",
                \"High error rate in API\"
            ],
        },
    }
}
