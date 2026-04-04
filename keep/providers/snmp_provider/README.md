# SNMP Provider for Keep

The SNMP provider allows Keep to receive SNMP traps and convert them into alerts.

## Configuration

The SNMP provider is a **consumer** provider, meaning it listens for incoming data.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `port` | `int` | Yes | `1162` | Port to listen for traps. |
| `community` | `str` | Yes | `public` | SNMP v1/v2c Community string. |

## Usage

When initialized, the SNMP provider starts a listener on the specified port.
Incoming SNMP traps are parsed, and the variable bindings are stored in the alert data.

### Example SNMP Trap Mapping
A trap with OID `1.3.6.1.6.3.1.1.4.1.0` (standard for `snmpTrapOID`) will be converted to an alert with:
- **Name**: `SNMP Trap: 1.3.6.1.6.3.1.1.4.1.0`
- **Severity**: `CRITICAL`
- **Payload**: Full JSON-formatted trap data.
