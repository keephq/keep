You can test the nagios provider implementation locally using mock alerts.
You'd need
- Python 3.8+
- Keep Platform running locally
- Keep Codebase Access

1. Clone Repo & navigate to `nagios_provider` repo
2. `ALERTS_MOCK.py` contains sample Nagios alerts covering different scenarios:
    - Service alerts (OK, CRITICAL, WARNING, UNKNOWN states)
    - Host alerts (UP, DOWN, UNREACHABLE states)
3. Run the test script:
```
python test_nagios.py
```
4. You can Also simulate webhook calls that Nagios would make:
    1. For service alerts;-

    ```
    curl -X POST -H "Content-Type: application/json" -d '{
        "host_name": "web-server-01",
        "service_description": "HTTP",
        "service_state": "CRITICAL",
        "timestamp": "2024-01-01T10:00:00Z",
        "output": "HTTP CRITICAL - Connection refused"
    }' http://localhost:YOUR_PORT/webhook/nagios
    ```

    2. For host alerts;-
    
    ```
    curl -X POST -H "Content-Type: application/json" -d '{
        "host_name": "web-server-01",
        "host_state": "DOWN",
        "timestamp": "2024-01-01T10:00:00Z",
        "output": "PING CRITICAL - Packet loss = 100%"
    }' http://localhost:YOUR_PORT/webhook/nagios
    ```