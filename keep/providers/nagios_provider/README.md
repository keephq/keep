# Nagios Provider

## Overview

The Nagios provider allows you to pull alerts from [Nagios XI](https://www.nagios.org/) and receive webhook notifications from Nagios.

## Authentication

The Nagios provider requires:

- **Nagios XI URL**: The base URL of your Nagios XI installation (e.g., `https://nagios.example.com/nagiosxi`)
- **API Key**: A Nagios XI API key with read access. You can generate one in **Admin > Manage API Keys** in the Nagios XI web interface.

## Connecting

### Pull (Polling)

The provider polls the Nagios XI REST API for:
- **Service status**: Services in WARNING, CRITICAL, or UNKNOWN state
- **Host status**: Hosts in DOWN or UNREACHABLE state

### Push (Webhook)

You can configure Nagios to send alerts to Keep via webhook:

1. Create a custom notification command in Nagios that sends a POST request to Keep's webhook endpoint.
2. Configure the command to include the alert data as a JSON payload.

Example notification command:
```bash
/usr/bin/curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: {api_key}" \
  -d '{
    "host_name": "$HOSTNAME$",
    "service_description": "$SERVICEDESC$",
    "state": "$SERVICESTATE$",
    "output": "$SERVICEOUTPUT$",
    "type": "service",
    "notification_type": "$NOTIFICATIONTYPE$",
    "address": "$HOSTADDRESS$",
    "timestamp": "$LONGDATETIME$"
  }' \
  {keep_webhook_api_url}
```

## Supported Features

- **Pull alerts**: Fetch current service and host problems from Nagios XI
- **Push alerts**: Receive webhook notifications from Nagios
- **Acknowledge problems**: Acknowledge host and service problems via Keep

## Useful Links

- [Nagios XI REST API Documentation](https://www.nagios.org/documentation/)
- [Nagios XI API Key Management](https://assets.nagios.com/downloads/nagiosxi/docs/Accessing-and-Using-the-XI-REST-API.pdf)
