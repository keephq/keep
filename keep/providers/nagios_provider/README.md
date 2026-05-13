## Nagios Provider

The Nagios provider allows ingesting alerts from Nagios Core via Livestatus or webhook.

### Features

- **Livestatus Integration**: Poll unacknowledged service problems from Nagios
- **Actions**: Acknowledge problems, schedule downtime, remove acknowledgement
- **Webhook Support**: Receive alerts via HTTP webhook

### Configuration

#### Livestatus Connection

To use Livestatus, ensure your Nagios instance has Livestatus enabled:

```bash
# Install mk-livestatus
sudo -S -p '' apt-get install nagios3 libnagios-objectwrapper-perl

# Configure nagios.cfg
broker_module=/usr/lib/nagios/brokers/livestatus.o socket=/var/lib/nagios/odbc/livestatus.sock
```

#### Webhook Configuration

In your Nagios configuration, add a notification command:

```
define command {
    command_name    keep-webhook
    command_line    /usr/local/bin/nagios_provider_script.js "$NOTIFICATIONTYPE$" "$HOSTNAME$" "$SERVICEDESC$" "$SERVICESTATE$" "$SERVICEOUTPUT$" "$LONGDATETIME$"
}
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NAGIOS_URL` | Nagios Frontend URL | Required |
| `LIVESTATUS_HOST` | Livestatus host | localhost |
| `LIVESTATUS_PORT` | Livestatus port | 6557 |
| `API_KEY` | Keep API key for webhook | Optional |

### Testing

Run the unit tests:

```bash
python -m pytest providers/nagios_provider/test_nagios_provider.py -v
```

### Reference

- [Nagios Livestatus](https://docs.nagios.org/nagioscore/en/livestatus)
- [Keep Documentation](https://docs.keephq.dev)
