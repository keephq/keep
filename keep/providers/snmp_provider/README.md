# SNMP Provider

The SNMP Provider allows Keep to interact with network devices using the SNMP protocol. It supports both polling specific OIDs and receiving SNMP Traps.

## Authentication Configuration

| Field | Description | Default |
|-------|-------------|---------|
| `host` | The SNMP host to poll (e.g., `192.168.1.1`) | - |
| `port` | The SNMP port for polling | `161` |
| `community` | SNMP Community string (for v1/v2c) | `public` |
| `version` | SNMP version (`1`, `2c`, or `3`) | `2c` |
| `trap_port` | Port to listen for SNMP Traps | `162` |
| `user` | SNMP v3 User | - |
| `auth_key` | SNMP v3 Authentication Key | - |
| `priv_key` | SNMP v3 Privacy Key | - |

## Capabilities

### Polling OIDs

You can poll one or more OIDs from a device using the `query` method.

```yaml
steps:
  - name: get-sysdescr
    provider:
      type: snmp
      config: "{{ providers.my-snmp-device }}"
      with:
        oids:
          - "1.3.6.1.2.1.1.1.0"
```

### Receiving Traps

When configured, Keep will start an SNMP Trap listener on the specified `trap_port`. Received traps are automatically converted into Keep alerts.

Note: Listening on port `162` typically requires root privileges. If running in a container, ensure the port is mapped correctly or use a non-privileged port (>1024).

## Dependencies

This provider requires the `pysnmp-lextudio` package.
