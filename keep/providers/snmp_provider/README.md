# SNMP Provider

The SNMP provider receives normalized SNMP trap or event payloads through Keep's
webhook endpoint and converts them into Keep alerts.

Use this provider with an SNMP trap receiver or relay that forwards traps as JSON
to Keep:

```text
POST /alerts/event/snmp?provider_id=<provider-id>
```

Recommended payload fields:

- `trap_oid` or `oid`: trap object identifier
- `source_ip`, `agent_address`, or `host`: trap source
- `timestamp`, `received_at`, or `time`: event timestamp
- `severity` or `level`: optional severity override
- `status` or `state`: optional status override
- `varbinds`: list or map of SNMP variable bindings

Example:

```json
{
  "trap_oid": "1.3.6.1.6.3.1.1.5.3",
  "source_ip": "10.0.0.12",
  "timestamp": "2026-05-13T08:15:00Z",
  "severity": "critical",
  "varbinds": [
    {
      "oid": "1.3.6.1.2.1.1.5.0",
      "name": "sysName",
      "value": "core-switch-1"
    },
    {
      "oid": "1.3.6.1.2.1.2.2.1.2.42",
      "name": "ifDescr",
      "value": "xe-0/0/42"
    }
  ]
}
```

The short demo video for this provider lives at
`keep/providers/snmp_provider/demo/snmp-provider-demo.webm`.
