# Instructions for a quick setup

## Setting up Graylog (v6)

### Installation

1. Spin up Graylog, [docs](https://go2docs.graylog.org/6-0/downloading_and_installing_graylog/docker_installation.htm)
   ```bash
   cd keep/providers/graylog_provider
   docker compose up
   ```
2. Once the containers are up and running, go to [http://localhost:9000](http://localhost:9000) and sign in with
   username `admin` & password `admin`.

### Getting Access Token

1. Navigate to System > Users and Teams to view the Users Overview page.
2. For the user `Admin`, select Edit tokens from the More drop-down menu.
3. Enter a token name, then click Create Token.

### Setting up Inputs and Event Definition

```python
import requests

auth = ("YOUR_ACCESS_TOKEN", "token")  # from the previous step
headers = {
 "Accept": "application/json",
 "X-Requested-By": "Keep",
 "Content-Type": "application/json",
}

input_data = {
 'type': 'org.graylog2.inputs.raw.tcp.RawTCPInput',
 'configuration': {
     'bind_address': '0.0.0.0',
     'port': 5044,
     'recv_buffer_size': 1048576,
     'number_worker_threads': 3,
     'tls_cert_file': '',
     'tls_key_file': '',
     'tls_enable': False,
     'tls_key_password': '',
     'tls_client_auth': 'disabled',
     'tls_client_auth_cert_file': '',
     'tcp_keepalive': False,
     'use_null_delimiter': False,
     'max_message_size': 2097152,
     'override_source': None,
     'charset_name': 'UTF-8',
 },
 'title': 'Keep-Input',
 'global': True,
}

input_response = requests.post(
 url="http://127.0.0.1:9000/api/system/inputs",
 headers=headers,
 json=input_data,
 auth=auth,
)

print(input_response.text)

event_data = {
 'title': 'Keep-Event',
 'description': 'This is an event for Keep',
 'priority': 3,
 'config': {
     'query': 'source:*',
     'query_parameters': [],
     'streams': [],
     'filters': [],
     'search_within_ms': 86400000,
     'execute_every_ms': 60000,
     'event_limit': 100,
     'group_by': [],
     'series': [],
     'conditions': {},
     'type': 'aggregation-v1',
 },
 'field_spec': {},
 'key_spec': [],
 'notification_settings': {
     'grace_period_ms': 300000,
     'backlog_size': None,
 },
 'notifications': [],
 'alert': True,
}

event_response = requests.post(
 url="http://127.0.0.1:9000/api/events/definitions",
 headers=headers,
 json=event_data,
 auth=auth,
)

print(event_response.text)
```

### Sending a log

1. After that you can send a plain text message to the Graylog raw/plaintext TCP input running on port 5044 using the
   following command:
   ```bash
   echo 'First log message' | nc localhost 5044 # @tb: it used to be 5555 but what worked for me was 5044
   ```

## Setup Keep to receive from Graylog

---

### **Note**

1. Run without `NGROK`
2. After Step 2, do this:
   - Go to Alerts > Notifications
   - Click the `title` of the newly create notification > `Edit Notification` > Replace `0.0.0.0` with your ip
     address > Click `Add to URL whitelist ` > Fill in the `Title` > `Update Configuration` > `Update Notification`

---

1. Go to `Providers` > search for `Graylog` >

   - Username: `admin`
   - Graylog Access Token: Access tokens from previous steps
   - Deployment Url: http://localhost:9000
   - Install webhook: True

2. This will create a new notification and install that notification in the existing events.
3. Send a log to `Graylog`, this will trigger an alert.
4. Check your feed.
