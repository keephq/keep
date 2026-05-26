# SNMP Provider

The SNMP provider opens a UDP listener (default port 162) and converts incoming
SNMPv1 / SNMPv2c traps into Keep alerts.

## Configuration

| Field              | Default     | Description                                        |
| ------------------ | ----------- | -------------------------------------------------- |
| `listen_host`      | `0.0.0.0`   | Interface to bind on                               |
| `listen_port`      | `162`       | UDP port (use a high port to avoid root)           |
| `community_string` | `public`    | SNMPv1 / v2c community string                      |
| `snmp_version`     | `v2c`       | `v1` or `v2c` (v3 not yet supported)               |

## Local smoke test

Start the listener on an unprivileged port:

```bash
KEEP_API_URL=http://localhost:8080 \
poetry run python -m keep.providers.snmp_provider.snmp_provider
```

Send a test trap with `snmptrap` (from `net-snmp`):

```bash
snmptrap -v 2c -c public 127.0.0.1:1162 \
  '' 1.3.6.1.6.3.1.1.5.3 \
  1.3.6.1.2.1.2.2.1.1.2 i 2
```

Each trap produces one alert; the trap OID is used as the alert name and
fingerprint, and every var bind is mirrored into `labels`.
