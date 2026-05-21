# SNMP Provider

The SNMP provider opens a UDP listener (default port 162) to ingest SNMP traps as Keep alerts, and supports active polling (GET/GETBULK) of SNMP devices.

## Features

- **Trap Ingestion**: Listens for SNMPv1, v2c, and v3 traps.
- **Active Polling**: Perform SNMP GET and GETBULK queries.
- **SNMPv3 Support**: Full USM support (MD5/SHA/SHA-2 auth, DES/AES privacy).
- **MIB Management**: Support for custom MIB files for human-readable OID and value translation.
- **EngineID Persistence**: Configurable EngineID for stable SNMPv3 communication.

## Configuration

| Field              | Default     | Description                                        |
| ------------------ | ----------- | -------------------------------------------------- |
| `listen_host`      | `0.0.0.0`   | Interface to bind the trap listener on             |
| `listen_port`      | `162`       | UDP port for traps (ports < 1024 require root)      |
| `community_string` | `public`    | SNMPv1 / v2c community string                      |
| `snmp_version`     | `v2c`       | `v1`, `v2c`, or `v3`                               |
| `v3_user`          |             | SNMPv3 Username                                    |
| `v3_auth_key`      |             | SNMPv3 Authentication Key                          |
| `v3_auth_protocol` | `usmHMACMD5AuthProtocol` | SNMPv3 Authentication Protocol (MD5, SHA, etc.) |
| `v3_priv_key`      |             | SNMPv3 Privacy Key                                 |
| `v3_priv_protocol` | `usmDESPrivProtocol` | SNMPv3 Privacy Protocol (DES, AES-128, etc.)    |
| `v3_engine_id`     |             | Persistent SNMP Engine ID (Hex string)              |
| `mibs_path`        |             | Path to custom MIB files directory                 |

## SNMP Query

You can perform SNMP queries via workflows or the Keep UI.

### Parameters

- `host`: Target device hostname or IP.
- `port`: SNMP port (default 161).
- `oids`: List of OIDs to query.
- `operation`: `get` (default) or `bulk`.
- `community`: Override the default community string.
- `version`: Override the default SNMP version.
- `non_repeaters`: For GETBULK, number of objects that are not to be repeated.
- `max_repetitions`: For GETBULK, maximum number of repetitions.

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
