## Nagios Provider

[Nagios](https://www.nagios.org/) is a widely-used open source monitoring tool for systems, networks, and infrastructure.

### Integration Type
Webhook-based — Nagios sends alerts to Keep via custom notification commands using curl.

### Setup

1. Define notification commands in your Nagios configuration (`/usr/local/nagios/etc/objects/commands.cfg`):

**Service notifications:**
```
define command {
    command_name    notify-keep
    command_line    /usr/bin/curl -s -X POST \
      -H "Content-Type: application/json" \
      -H "X-API-KEY: $USER1$" \
      $USER2$ \
      -d '{"host_name":"$HOSTNAME$","service_description":"$SERVICEDESC$","state":"$SERVICESTATE$","state_type":"$SERVICESTATETYPE$","plugin_output":"$SERVICEOUTPUT$","long_plugin_output":"$LONGSERVICEOUTPUT$","notification_type":"$NOTIFICATIONTYPE$","host_state":"$HOSTSTATE$","host_address":"$HOSTADDRESS$","timestamp":"$TIMET$","current_attempt":"$SERVICEATTEMPT$","max_attempts":"$MAXSERVICEATTEMPTS$","duration":"$SERVICEDURATION$","contact_name":"$CONTACTNAME$","contact_email":"$CONTACTEMAIL$","acknowledgement_author":"$NOTIFICATIONAUTHORALIAS$","acknowledgement_comment":"$NOTIFICATIONCOMMENT$"}'
}
```

**Host notifications:**
```
define command {
    command_name    notify-keep-host
    command_line    /usr/bin/curl -s -X POST \
      -H "Content-Type: application/json" \
      -H "X-API-KEY: $USER1$" \
      $USER2$ \
      -d '{"host_name":"$HOSTNAME$","state":"$HOSTSTATE$","state_type":"$HOSTSTATETYPE$","plugin_output":"$HOSTOUTPUT$","long_plugin_output":"$LONGHOSTOUTPUT$","notification_type":"$NOTIFICATIONTYPE$","host_address":"$HOSTADDRESS$","timestamp":"$TIMET$","current_attempt":"$HOSTATTEMPT$","max_attempts":"$MAXHOSTATTEMPTS$","duration":"$HOSTDURATION$","contact_name":"$CONTACTNAME$","contact_email":"$CONTACTEMAIL$","acknowledgement_author":"$NOTIFICATIONAUTHORALIAS$","acknowledgement_comment":"$NOTIFICATIONCOMMENT$"}'
}
```

2. Set resource macros in `/usr/local/nagios/etc/resource.cfg`:
```
$USER1$=your-keep-api-key
$USER2$=https://your-keep-instance/alerts/event/nagios
```

3. Assign commands to contacts:
```
define contact {
    ...
    service_notification_commands   notify-keep
    host_notification_commands      notify-keep-host
}
```

4. Restart Nagios: `sudo systemctl restart nagios`

### Supported Alert Types
- **Service states:** OK, WARNING, CRITICAL, UNKNOWN
- **Host states:** UP, DOWN, UNREACHABLE
- **Notification types:** PROBLEM, RECOVERY, ACKNOWLEDGEMENT, FLAPPINGSTART, FLAPPINGSTOP, DOWNTIMESTART, DOWNTIMEEND

### Deduplication
Alerts are fingerprinted by `host_name` + `service_description`.
