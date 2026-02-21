# SNMP Provider

The SNMP provider allows Keep to receive SNMP traps and events as alerts via webhook-based ingestion.

## Overview

[SNMP (Simple Network Management Protocol)](https://en.wikipedia.org/wiki/Simple_Network_Management_Protocol) is the standard protocol for monitoring and managing network devices. SNMP traps are unsolicited notifications sent by network devices (routers, switches, servers) to alert management systems about events like interface failures, device reboots, or authentication errors.

Keep's SNMP provider ingests these traps via a webhook endpoint, supporting SNMPv1, SNMPv2c, and SNMPv3 trap formats.

## Features

- **Multi-version support:** Handles SNMPv1, SNMPv2c, and SNMPv3 trap formats
- **Well-known trap mapping:** Automatically maps standard SNMP traps (linkDown, linkUp, coldStart, etc.) to appropriate severity levels
- **Resolution detection:** linkUp traps are automatically mapped to RESOLVED status
- **Flexible varbind parsing:** Accepts varbinds as dict, list, or raw text
- **Custom severity mapping:** Override severity via the webhook payload
- **Enterprise trap support:** Handles vendor-specific enterprise traps

## Severity Mapping

| SNMP Trap | Keep Severity |
|-----------|---------------|
| coldStart | WARNING |
| warmStart | INFO |
| linkDown | CRITICAL |
| linkUp | INFO |
| authenticationFailure | WARNING |
| egpNeighborLoss | WARNING |
| Enterprise-specific | WARNING (default, overridable) |

## Setup

### Using snmptrapd (Net-SNMP)

The most common setup uses `snmptrapd` from the Net-SNMP package as a trap receiver, with a handler script that forwards traps to Keep's webhook.

1. Install Net-SNMP on your trap receiver host
2. Create a handler script that parses trap data and POSTs JSON to Keep
3. Configure snmptrapd to use the handler
4. Point your network devices' SNMP trap destination to the snmptrapd host

See the webhook setup instructions in Keep's UI for detailed configuration steps.

### Direct JSON Integration

Any system that can send HTTP POST requests with JSON can integrate directly:

```bash
curl -X POST https://your-keep-instance/alerts/event/snmp \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{
    "version": "v2c",
    "oid": "1.3.6.1.6.3.1.1.5.3",
    "agent_address": "192.168.1.100",
    "hostname": "switch01",
    "description": "Interface down",
    "varbinds": {"1.3.6.1.2.1.2.2.1.2": "GigabitEthernet0/1"}
  }'
```

## Webhook Payload Format

### Required Fields

| Field | Description |
|-------|-------------|
| `version` | SNMP version: `v1`, `v2c`, or `v3` |

### Optional Fields

| Field | Description |
|-------|-------------|
| `oid` | Trap OID (e.g., `1.3.6.1.6.3.1.1.5.3` for linkDown) |
| `agent_address` | IP address of the SNMP agent |
| `hostname` | Hostname of the device |
| `community` | SNMP community string |
| `severity` | Override severity (`critical`, `major`, `minor`, `warning`, `info`) |
| `description` | Human-readable description of the event |
| `varbinds` | Variable bindings as a dict of OID:value pairs |
| `generic_trap` | SNMPv1 generic trap type (0-6) |
| `specific_trap` | SNMPv1 specific trap type |
| `enterprise` | SNMPv1 enterprise OID |
