# SolarWinds Provider

Pulls active alerts from [SolarWinds Orion](https://www.solarwinds.com/) via the
SolarWinds Information Service (SWIS) REST API.

## Authentication

The provider authenticates against SWIS with HTTP Basic auth — the same
username and password you would use to log into the Orion Web Console. SWIS
listens on port `17778` by default.

| Field        | Required | Description                                                                 |
|--------------|----------|-----------------------------------------------------------------------------|
| `host_url`   | yes      | Base URL of the Orion server, e.g. `https://orion.example.com:17778`.       |
| `username`   | yes      | Orion account username with read access to alerts.                           |
| `password`   | yes      | Orion account password.                                                      |
| `verify_ssl` | no       | Set to `false` if your Orion server uses a self-signed certificate.          |

A read-only Orion account is sufficient — the provider only issues `SELECT`
queries against `Orion.AlertActive`, `Orion.AlertObjects` and
`Orion.AlertConfigurations`.

## What the provider pulls

On each poll, Keep runs the following SWQL query against SWIS:

```sql
SELECT a.AlertActiveID, a.AlertObjectID, a.TriggeredDateTime,
       a.TriggeredMessage, a.Acknowledged, a.AcknowledgedBy,
       a.AcknowledgedDateTime,
       ao.AlertID, ao.EntityCaption, ao.EntityType, ao.RelatedNodeCaption,
       ac.Name AS AlertName, ac.Severity, ac.Description
FROM Orion.AlertActive a
INNER JOIN Orion.AlertObjects ao ON a.AlertObjectID = ao.AlertObjectID
INNER JOIN Orion.AlertConfigurations ac ON ao.AlertID = ac.AlertID
```

Each row becomes an `AlertDto` in Keep with:

- `id` — the Orion `AlertObjectID`, stable across re-polls so the same
  active alert is deduped (no spurious "new" alerts on every cycle).
- `name` — the human-readable name configured on the Orion alert.
- `severity` — mapped from Orion's numeric severity (`0`=Informational →
  `4`=Critical) to Keep's severity scale.
- `status` — `acknowledged` if the alert has been acknowledged in Orion,
  otherwise `firing`.
- `lastReceived` — the alert's `TriggeredDateTime`.
- Extra fields kept on the alert for downstream workflows:
  `alert_object_id`, `alert_active_id`, `alert_id`, `entity_type`,
  `entity_caption`, `related_node_caption`, `acknowledged`,
  `acknowledged_by`, `acknowledged_at`.

## Severity mapping

| Orion severity | Keep severity |
|----------------|---------------|
| `0` Informational | `info`     |
| `1` Notice        | `low`      |
| `2` Warning       | `warning`  |
| `3` Serious       | `high`     |
| `4` Critical      | `critical` |

## Reference

- [SolarWinds Information Service (SWIS) overview](https://documentation.solarwinds.com/en/success_center/orionplatform/content/core-using-the-information-service.htm)
- [SWQL query reference](https://github.com/solarwinds/OrionSDK/wiki/About-SWQL)
