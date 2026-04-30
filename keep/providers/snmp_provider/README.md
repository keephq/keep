# SNMP Provider

Monitor network devices via the Simple Network Management Protocol (SNMP).

## Features

- **SNMP GET**: Query a single OID from a network device
- **SNMP WALK**: Walk an entire OID subtree
- **Pull Alerts**: Monitor interface status (IF-MIB) and host resources (HOST-RESOURCES-MIB)
- **Receive Traps**: Process incoming SNMP trap notifications

## Authentication

Supports SNMP v1, v2c, and v3:

| Field | Description |
|-------|-------------|
| host | Device IP or hostname |
| port | UDP port (default: 161) |
| community | Community string (v1/v2c) |
| version | 1, 2c, or 3 |

For SNMPv3:

| Field | Description |
|-------|-------------|
| security_name | Username |
| auth_protocol | MD5 or SHA |
| auth_key | Authentication passphrase |
| priv_protocol | DES, AES128, AES192, AES256 |
| priv_key | Privacy passphrase |

## Configuration



## Usage

### Query OIDs



### Walk a Subtree



## Common OIDs

| OID | Name | Description |
|-----|------|-------------|
| 1.3.6.1.2.1.1.1.0 | sysDescr | System description |
| 1.3.6.1.2.1.1.5.0 | sysName | System name |
| 1.3.6.1.2.1.2.2.1.8 | ifOperStatus | Interface operational status |
| 1.3.6.1.2.1.2.2.1.2 | ifDescr | Interface description |
| 1.3.6.1.2.1.2.2.1.5 | ifSpeed | Interface speed |
| 1.3.6.1.2.1.25.3.2.1.5 | hrDeviceStatus | Host resource device status |

## Triggers / Webhook

The SNMP provider can receive SNMP traps via the Keep webhook endpoint:



SNMP trap data is formatted into Keep alerts via .
