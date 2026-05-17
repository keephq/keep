# Nagios Provider

The Nagios provider polls the Nagios XI REST API for host and service status.

## Configuration

- `host_url`: Nagios XI URL, for example `https://nagios.example.com` or `https://nagios.example.com/nagiosxi`
- `api_key`: Nagios XI API key

## Setup

1. In Nagios XI, create or copy an API key from the user account that Keep should use.
2. Add a Nagios provider in Keep with the Nagios XI URL and API key.
3. Keep polls:
   - `/nagiosxi/api/v1/objects/hoststatus`
   - `/nagiosxi/api/v1/objects/servicestatus`

## State Mapping

| Nagios state | Keep status | Keep severity |
| --- | --- | --- |
| 0 OK / UP | resolved | low |
| 1 WARNING | firing | warning |
| 2 CRITICAL / DOWN | firing | critical |
| 3 UNKNOWN | firing | info |

Acknowledged Nagios problems are returned with Keep's `acknowledged` status while preserving the original Nagios state in labels.

## Troubleshooting

- Confirm the API key can access `objects/hoststatus` and `objects/servicestatus`.
- If your Nagios XI URL already includes `/nagiosxi`, keep it in `host_url`; otherwise Keep appends it automatically.
- Nagios Core CGI polling and webhook notification commands are not part of this provider scope.
