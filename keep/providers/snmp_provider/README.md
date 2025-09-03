# SNMP Provider

The SNMP Provider enables Keep to receive SNMP traps from network devices and convert them into actionable alerts.

## Features

- **Multi-Protocol Support**: SNMPv1, SNMPv2c, and SNMPv3
- **Security**: Full SNMPv3 authentication and privacy support
- **Automatic Severity Mapping**: Maps standard SNMP traps to appropriate alert severities
- **Rich Context**: Extracts system information and trap variables
- **Configurable**: Flexible listening address and port configuration

## Supported SNMP Versions

### SNMPv1 & SNMPv2c
- Community string authentication
- Basic trap reception

### SNMPv3
- **Authentication Protocols**: MD5, SHA
- **Privacy Protocols**: DES, AES
- **Security Levels**: 
  - noAuthNoPriv (no authentication, no privacy)
  - authNoPriv (authentication, no privacy)
  - authPriv (authentication and privacy)

## Configuration

### Basic SNMPv1/v2c Configuration

```yaml
authentication:
  listen_address: "0.0.0.0"
  listen_port: 162
  community_string: "public"
```

### Advanced SNMPv3 Configuration

```yaml
authentication:
  listen_address: "0.0.0.0"
  listen_port: 162
  community_string: "public"  # For v1/v2c fallback
  security_name: "snmpuser"
  auth_protocol: "SHA"        # MD5 or SHA
  auth_key: "authpassword123"
  priv_protocol: "AES"        # DES or AES
  priv_key: "privpassword123"
```

## Standard SNMP Trap Mappings

The provider automatically maps standard SNMP traps to appropriate severities:

| Trap Type | OID | Severity | Description |
|-----------|-----|----------|-------------|
| coldStart | 1.3.6.1.6.3.1.1.5.1 | INFO | System cold start |
| warmStart | 1.3.6.1.6.3.1.1.5.2 | INFO | System warm start |
| linkDown | 1.3.6.1.6.3.1.1.5.3 | WARNING | Interface down |
| linkUp | 1.3.6.1.6.3.1.1.5.4 | INFO | Interface up |
| authenticationFailure | 1.3.6.1.6.3.1.1.5.5 | HIGH | Authentication failure |

## Alert Fields

Generated alerts include:

- **name**: Trap type or OID
- **description**: Detailed trap information
- **severity**: Mapped from trap type
- **source**: Agent address
- **fingerprint**: Unique trap identifier
- **labels**: System information and trap variables

## Network Configuration

### Firewall Rules
Ensure UDP port 162 (or your configured port) is open for incoming SNMP traps.

### Device Configuration
Configure your network devices to send SNMP traps to Keep's listening address and port.

## Troubleshooting

### Common Issues

1. **Port Permission**: Port 162 requires root privileges on Linux. Consider using a higher port (e.g., 1162) or running with appropriate permissions.

2. **Firewall**: Ensure the listening port is open in your firewall configuration.

3. **SNMPv3 Authentication**: Verify that authentication and privacy keys match between the device and Keep configuration.

## Testing

You can test the SNMP provider using the `snmptrap` command:

```bash
# SNMPv2c test trap
snmptrap -v2c -c public localhost:162 '' 1.3.6.1.6.3.1.1.5.1

# SNMPv3 test trap
snmptrap -v3 -u snmpuser -a SHA -A authpassword123 -x AES -X privpassword123 \
         localhost:162 '' 1.3.6.1.6.3.1.1.5.1
```

## Provider Scopes

The SNMP provider defines the following scope:

- **receive_traps**: Required scope for receiving SNMP traps from network devices

## Implementation Details

### Architecture

The SNMP provider uses the `pysnmp-lextudio` library to implement:

1. **SNMP Engine**: Handles protocol-level SNMP operations
2. **Transport Layer**: UDP transport for receiving traps
3. **Notification Receiver**: Processes incoming SNMP notifications
4. **Alert Formatter**: Converts SNMP data to Keep AlertDto objects

### Automatic Startup

The SNMP trap receiver starts automatically when the provider is initialized and configured. The receiver runs in a separate thread to avoid blocking the main application.

### Resource Management

- Proper cleanup of SNMP engine and transport resources
- Thread-safe trap receiver management
- Graceful shutdown handling

### Error Handling

- Comprehensive error logging for troubleshooting
- Graceful handling of malformed traps
- Configuration validation with detailed error messages

## Security Considerations

### SNMPv3 Security

- **Authentication**: Protects against message tampering
- **Privacy**: Encrypts SNMP messages
- **User-based Security Model (USM)**: Provides per-user security settings

### Network Security

- Consider using firewall rules to restrict SNMP trap sources
- Use strong authentication and privacy keys for SNMPv3
- Monitor for authentication failures and suspicious activity

## Performance

### Scalability

- Asynchronous trap processing prevents blocking
- Efficient OID-to-severity mapping
- Minimal memory footprint per trap

### Monitoring

Monitor the following metrics:
- Trap reception rate
- Processing latency
- Authentication failures
- Resource utilization

## Integration Examples

### Cisco Devices

```
snmp-server enable traps
snmp-server host <keep-server-ip> version 2c public
```

### Linux Net-SNMP

```
# /etc/snmp/snmptrapd.conf
traphandle default /usr/bin/snmptrap -v2c -c public <keep-server-ip>:162
```

### Windows SNMP Service

Configure SNMP service to send traps to Keep server through Windows SNMP Service configuration.
