## Nagios Provider

Webhook-based integration that receives Nagios host and service notifications in Keep.

### Supported Notification Types

- **Host notifications**: UP, DOWN, UNREACHABLE
- **Service notifications**: OK, WARNING, CRITICAL, UNKNOWN
- **Notification types**: PROBLEM, RECOVERY, ACKNOWLEDGEMENT, FLAPPINGSTART, FLAPPINGSTOP, DOWNTIMESTART, DOWNTIMEEND, DOWNTIMECANCELLED

### Setup

1. Add the following command definition to your Nagios configuration (`commands.cfg`):

```cfg
define command{
  command_name    notify-keep-host
  command_line    /usr/bin/curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-KEY: $USER1$" \
    -d '{"host_name":"$HOSTNAME$","host_state":"$HOSTSTATE$","host_output":"$HOSTOUTPUT$","notification_type":"$NOTIFICATIONTYPE$","host_address":"$HOSTADDRESS$"}' \
    YOUR_KEEP_WEBHOOK_URL
}

define command{
  command_name    notify-keep-service
  command_line    /usr/bin/curl -s -X POST \
    -H "Content-Type: application/json" \
    -H "X-API-KEY: $USER1$" \
    -d '{"host_name":"$HOSTNAME$","host_state":"$HOSTSTATE$","host_output":"$HOSTOUTPUT$","service_description":"$SERVICEDESC$","service_state":"$SERVICESTATE$","service_output":"$SERVICEOUTPUT$","notification_type":"$NOTIFICATIONTYPE$"}' \
    YOUR_KEEP_WEBHOOK_URL
}
```

2. Create a contact that uses these commands:

```cfg
define contact{
  contact_name                    keep
  alias                           Keep Alert Manager
  service_notification_commands   notify-keep-service
  host_notification_commands      notify-keep-host
  service_notification_period     24x7
  host_notification_period        24x7
  service_notification_options    w,u,c,r
  host_notification_options       d,u,r
}
```

3. Add the contact to your contact groups or directly to hosts/services.

### Nagios XI

For Nagios XI, you can also use the built-in webhook notifications or configure custom commands through the Nagios XI web interface under **Configure > Core Config Manager > Commands**.

### Testing

Send a test webhook:

```bash
curl -X POST http://localhost:8080/alerts/event/nagios \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your-api-key" \
  -d '{"host_name":"testhost","host_state":"DOWN","host_output":"CRITICAL - Host unreachable","notification_type":"PROBLEM"}'
```
