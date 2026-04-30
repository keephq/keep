# SNMP Provider

Receive SNMP traps and poll SNMP devices as Keep alerts.

## Features

- **Push mode**: Background UDP listener converts incoming SNMP traps to Keep alerts in real-time
- **Pull mode**: Polls IF-MIB interface statuses on a target device
- **SNMPv1, v2c, v3**: Full USM support (SHA/MD5 auth, AES/DES privacy)
- **Automatic severity mapping**: Standard RFC 1215 traps map to HIGH/WARNING/INFO severity
- **Deduplication**: SHA-256 fingerprinting on `{host, trap_oid}` prevents duplicate alerts

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `listen_port` | `1162` | UDP port for incoming traps (use 162 with root) |
| `listen_address` | `0.0.0.0` | IP to bind trap receiver |
| `community_string` | `public` | SNMP v1/v2c community string |
| `snmp_version` | `2c` | SNMP version: `1`, `2c`, or `3` |
| `target_host` | *(blank)* | Device IP to poll (leave blank for trap-only mode) |
| `target_port` | `161` | Target device SNMP port |
| `v3_username` | *(blank)* | SNMPv3 USM username |
| `v3_auth_protocol` | `SHA` | SNMPv3 auth protocol: `SHA` or `MD5` |
| `v3_auth_key` | *(blank)* | SNMPv3 authentication passphrase |
| `v3_priv_protocol` | `AES` | SNMPv3 privacy protocol: `AES` or `DES` |
| `v3_priv_key` | *(blank)* | SNMPv3 privacy passphrase |

## Quick Start — Trap Receiver

1. Add the SNMP provider in Keep UI with `listen_port: 1162`
2. Configure your network devices to send traps to `<keep-host>:1162`
3. Traps appear as alerts automatically

## Quick Start — Device Polling

1. Add the SNMP provider with `target_host: 192.168.1.1`
2. Keep polls IF-MIB every alert refresh cycle
3. Non-operational interfaces generate HIGH severity alerts

## Sending a Test Trap

```bash
# Requires net-snmp tools
snmptrap -v 2c -c public <keep-host>:1162 '' 1.3.6.1.6.3.1.1.5.3
```

## Severity Mapping

| Trap | Severity | Status |
|------|----------|--------|
| `linkDown` | HIGH | FIRING |
| `linkUp` | INFO | RESOLVED |
| `authenticationFailure` | WARNING | FIRING |
| `coldStart` | WARNING | FIRING |
| `warmStart` | INFO | FIRING |
| `egpNeighborLoss` | HIGH | FIRING |
| Enterprise traps (Cisco/Juniper/Microsoft) | WARNING | FIRING |
| Unknown traps | WARNING | FIRING |

## Dependencies

```
pysnmp-lextudio>=6.2.7
```

> Note: `pysnmp-lextudio` is the actively maintained fork of pysnmp, compatible with Python 3.10+.
