# Nagios Provider

Integrates [Nagios](https://www.nagios.org/) (Core and XI) with Keep for alert ingestion.

## Modes of Operation

### Push (Webhook) Mode -- Nagios Core and XI

Nagios sends alert notifications to Keep in real time via a custom notification command.

**Setup:**

1. Add the following command to your Nagios configuration (e.g. `/usr/local/nagios/etc/objects/commands.cfg`):

```cfg
define command {
    command_name    notify_keep
    command_line    /usr/bin/curl -s -X POST \
        -H "Content-Type: application/json" \
        -H "X-API-KEY: $USER10$" \
        -d '{ \
            "host_name": "$HOSTNAME$", \
            "service_description": "$SERVICEDESC$", \
            "service_state": "$SERVICESTATE$", \
            "host_state": "$HOSTSTATE$", \
            "output": "$SERVICEOUTPUT$", \
            "timestamp": "$LONGDATETIME$", \
            "notification_type": "$NOTIFICATIONTYPE$" \
        }' \
        https://your-keep-instance/alerts/event/nagios
}
```

2. For host-only notifications, replace `$SERVICEOUTPUT$` with `$HOSTOUTPUT$` and omit `service_description` and `service_state`.

3. Assign `notify_keep` as the notification command for your contacts:

```cfg
define contact {
    ...
    service_notification_commands   notify_keep
    host_notification_commands      notify_keep
}
```

4. Restart Nagios to apply changes.

### Pull Mode -- Nagios XI Only

Keep periodically queries the Nagios XI REST API to fetch current non-OK service and host states.

**Requirements:**
- Nagios XI with REST API enabled
- An API key (generate one under Admin > Manage API Keys in the Nagios XI web UI)

**Configuration in Keep:**
- **Nagios XI Base URL**: e.g. `https://nagios.example.com`
- **API Key**: your Nagios XI API key

## Local Testing with Docker

You can spin up a local Nagios instance for testing using the `jasonrivers/nagios` Docker image:

```bash
docker run -d \
    --name nagios \
    -p 8080:80 \
    jasonrivers/nagios:latest
```

Access the Nagios web UI at `http://localhost:8080/nagios` (default credentials: `nagiosadmin` / `nagios`).

To test the webhook integration locally, you can use a tool like `ngrok` to expose your local Keep instance, then configure the notification command above to point at the tunnel URL.

For pull mode testing, note that the `jasonrivers/nagios` image runs Nagios Core (not XI), so you will need a Nagios XI trial instance or mock the API responses in your tests.
