## Nagios Provider for Keep

This provider allows Keep to receive alerts from Nagios XI and Nagios Core.

### Features
- **Pull Alerts:** Pulls service and host status from Nagios XI REST API.
- **Webhook:** Receive real-time alerts from Nagios Core/XI via custom notification scripts.

### Configuration
1. **Host URL:** The base URL of your Nagios installation (e.g., `http://nagios.example.com`).
2. **API Key (Optional):** Required for pulling alerts from Nagios XI.

### Nagios Core Webhook Setup
To send alerts from Nagios Core to Keep:
1. Define a new command in your `commands.cfg`:
```
define command {
    command_name notify-keep-webhook
    command_line /usr/bin/curl -X POST -H "Content-Type: application/json" -d "{ \"host_name\": \"$HOSTNAME$\", \"service_description\": \"$SERVICEDESC$\", \"state\": \"$SERVICESTATE$\", \"output\": \"$SERVICEOUTPUT$\" }" <KEEP_WEBHOOK_URL>
}
```
2. Add the command to your contacts or host/service notification definitions.
