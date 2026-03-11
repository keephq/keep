## Apache SkyWalking Setup

### Requirements
- Apache SkyWalking OAP Server v9.x or later

### Webhook Configuration

1. Open your SkyWalking OAP configuration at `config/alarm-settings.yml`
2. Add a webhook section:

```yaml
webhook:
  keep:
    is-default: true
    urls:
      - https://your-keep-instance.com/alerts/event/skywalking
    headers:
      X-API-KEY: your-keep-api-key
```

3. Restart the SkyWalking OAP server.

### Alert Format

SkyWalking sends alerts as a JSON array of alarm messages via HTTP POST:

```json
[{
  "scopeId": 1,
  "scope": "SERVICE",
  "name": "serviceA",
  "uuid": "unique-alarm-id",
  "id0": "service-id",
  "id1": "",
  "ruleName": "service_resp_time_rule",
  "alarmMessage": "Response time of service serviceA is more than 1000ms",
  "startTime": 1560524171000,
  "recoveryTime": null,
  "tags": [{"key": "level", "value": "WARNING"}]
}]
```

### Severity Mapping

SkyWalking alarm severity is determined by the `level` tag:

| SkyWalking Tag Value | Keep Severity |
|---------------------|---------------|
| CRITICAL / CRIT     | Critical      |
| HIGH                | High          |
| WARNING / WARN      | Warning       |
| LOW                 | Low           |
| INFO / OK           | Info          |

### Status Mapping

| Condition           | Keep Status   |
|--------------------|---------------|
| recoveryTime = null | Firing        |
| recoveryTime set    | Resolved      |

### Supported Scopes

- Service
- ServiceInstance
- Endpoint
- ServiceRelation
- ServiceInstanceRelation
- EndpointRelation

### Documentation

- [SkyWalking Alerting Documentation](https://skywalking.apache.org/docs/main/latest/en/setup/backend/backend-alarm/)
- [SkyWalking Official Site](https://skywalking.apache.org/)
