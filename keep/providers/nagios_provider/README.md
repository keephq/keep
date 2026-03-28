# Nagios Provider

## Overview

The Nagios provider integrates [Nagios](https://www.nagios.org/) monitoring with Keep.
It supports both **pull** (polling Nagios API for current status) and **push** (receiving
webhook notifications from Nagios) modes.

Both **Nagios XI** (commercial) and **Nagios Core** (open source) are supported.

## Authentication

| Field | Required | Description |
|---|---|---|
| `host_url` | Yes | Base URL of your Nagios instance, e.g. `https://nagios.example.com` |
| `api_key` | For Nagios XI | API key from **Admin > Manage API Keys** in Nagios XI |
| `username` | For Nagios Core | HTTP basic auth username |
| `password` | For Nagios Core | HTTP basic auth password |

## Pull Integration

When configured with credentials, Keep polls the Nagios API for:

- **Host status** — hosts in DOWN or UNREACHABLE state
- **Service status** — services in WARNING, CRITICAL, or UNKNOWN state

**Nagios XI** uses the REST API at `/nagiosxi/api/v1/objects/hoststatus` and `/servicestatus`.

**Nagios Core** uses the CGI JSON API at `/nagios/cgi-bin/statusjson.cgi`.

## Push Integration (Webhook)

Configure Nagios to POST alert notifications to Keep's webhook endpoint.

### Nagios XI

1. Go to **Admin > Notification Methods**.
2. Add a new notification method of type **Webhook**.
3. Set the webhook URL to your Keep webhook URL.
4. Add the HTTP header `x-api-key` with your Keep API key.

### Nagios Core

Add these commands to your Nagios configuration:

```bash
define command {
    command_name    notify-keep-host
    command_line    /usr/bin/curl -s -o /dev/null \
        -X POST $USER1$/keep_webhook_url$ \
        -H "x-api-key: $USER2$" \
        -H "Content-Type: application/json" \
        -d '{"type":"HOST","hostname":"$HOSTNAME$","hoststate":"$HOSTSTATE$","hostoutput":"$HOSTOUTPUT$","notificationtype":"$NOTIFICATIONTYPE$","datetime":"$LONGDATETIME$"}'
}

define command {
    command_name    notify-keep-service
    command_line    /usr/bin/curl -s -o /dev/null \
        -X POST $USER1$/keep_webhook_url$ \
        -H "x-api-key: $USER2$" \
        -H "Content-Type: application/json" \
        -d '{"type":"SERVICE","hostname":"$HOSTNAME$","servicedesc":"$SERVICEDESC$","servicestate":"$SERVICESTATE$","serviceoutput":"$SERVICEOUTPUT$","notificationtype":"$NOTIFICATIONTYPE$","datetime":"$LONGDATETIME$"}'
}
```

Then assign these commands as notification commands for your contacts.

## Useful Links

- [Nagios XI REST API Documentation](https://assets.nagios.com/downloads/nagiosxi/docs/Accessing-and-Using-the-XI-REST-API.pdf)
- [Nagios Core CGI API](https://www.nagios.org/developerinfo/externalcommands/)
- [Keep Documentation](https://docs.keephq.dev)
