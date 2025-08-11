# SNMP Provider

The SNMP Provider enables Keep to receive and process SNMP traps from network devices and convert them into Keep alerts.

## Features

- **Protocol Support**: SNMPv1, SNMPv2c, and SNMPv3
- **Authentication**: Community string for v1/v2c, USM for v3
- **Encryption**: DES and AES privacy protocols for SNMPv3
- **Automatic Severity Mapping**: Maps standard SNMP traps to appropriate alert severities
- **Rich Alert Context**: Extracts system information and trap variables into alert labels

## Configuration

### Basic Configuration (SNMPv1/v2c)

```yaml
authentication:
  listen_address: "0.0.0.0"      # IP address to listen on
  listen_port: 162               # UDP port (use 1162 for non-root)
  community_string: "public"     # Community string
```

### Advanced Configuration (SNMPv3)

```yaml
authentication:
  listen_address: "0.0.0.0"
  listen_port: 162
  community_string: "public"     # Still needed for v1/v2c compatibility
  security_name: "snmpuser"      # SNMPv3 username
  auth_protocol: "SHA"           # MD5 or SHA
  auth_key: "authpassword123"    # Min 8 characters
  priv_protocol: "AES"           # DES or AES
  priv_key: "privpassword123"    # Min 8 characters
```

## Severity Mapping

The provider automatically maps standard SNMP traps to Keep alert severities:

| Trap OID | Trap Type | Severity |
|----------|-----------|----------|
| 1.3.6.1.6.3.1.1.5.1 | Cold Start | INFO |
| 1.3.6.1.6.3.1.1.5.2 | Warm Start | INFO |
| 1.3.6.1.6.3.1.1.5.3 | Link Down | CRITICAL |
| 1.3.6.1.6.3.1.1.5.4 | Link Up | INFO |
| 1.3.6.1.6.3.1.1.5.5 | Authentication Failure | WARNING |
| 1.3.6.1.6.3.1.1.5.6 | EGP Neighbor Loss | WARNING |
| Other | Custom/Enterprise | WARNING |

## Testing

### Send Test Trap (Linux)

```bash
# SNMPv2c trap
snmptrap -v2c -c public localhost:1162 '' 1.3.6.1.6.3.1.1.5.3 \
  1.3.6.1.2.1.1.3.0 i 123456 \
  1.3.6.1.6.3.1.1.4.1.0 o 1.3.6.1.6.3.1.1.5.3 \
  1.3.6.1.2.1.1.5.0 s "test-router"
```

### Send Test Trap (Python)

```python
from pysnmp.hlapi import *

sendNotification(
    SnmpEngine(),
    CommunityData('public'),
    UdpTransportTarget(('localhost', 1162)),
    ContextData(),
    'trap',
    NotificationType(ObjectIdentity('1.3.6.1.6.3.1.1.5.3'))
)
```

## Notes

- Port 162 is the standard SNMP trap port but requires root/admin privileges
- Use port 1162 or higher for testing without special permissions
- The provider maintains a buffer of up to 1000 alerts in memory
- Alerts are retrieved and cleared when `_get_alerts()` is called