from datetime import datetime, timezone

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class AirflowProvider(BaseProvider):
    """Enrich alerts with data sent from Airflow."""

    PROVIDER_DISPLAY_NAME = "Airflow"
    PROVIDER_CATEGORY = ["Orchestration"]
    FINGERPRINT_FIELDS = ["fingerprint"]

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on configuring Airflow to send alerts to Keep, refer to the [Keep documentation](https://docs.keephq.dev/providers/documentation/airflow-provider).

### 1. Configure Keep's Webhook Credentials
To send alerts to Keep, set up the webhook URL and API key:

- **Keep Webhook URL**: {keep_webhook_api_url}
- **Keep API Key**: {api_key}

### 2. Configure Airflow to Send Alerts to Keep
Airflow uses a callback function to send alerts to Keep. Below is an example configuration:

```python
import os
import requests

def task_failure_callback(context):
    # Replace with your specific Keep webhook URL if different.
    keep_webhook_url = "{keep_webhook_api_url}"
    api_key = "{api_key}"

    headers = {{
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-KEY": api_key,
    }}

    data = {{
        "name": f"Airflow Task Failure",
        "message": f"Task failed in DAG",
        "status": "firing",
        "service": "pipeline",
        "severity": "critical",
    }}

    response = requests.post(keep_webhook_url, headers=headers, json=data)
    response.raise_for_status()
```

### 3. Attach the Callback to the DAG
Attach the failure callback to the DAG using the `on_failure_callback` parameter:

```python
from airflow import DAG
from datetime import datetime

dag = DAG(
    dag_id="keep_dag",
    default_args=default_args,
    description="A simple DAG with Keep integration",
    schedule_interval=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    on_failure_callback=task_failure_callback,
)
```
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        pass

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        alert = AlertDto(
            id=event.get("fingerprint"),
            fingerprint=event.get("fingerprint"),
            name=event.get("name", "Airflow Alert"),
            message=event.get("message"),
            description=event.get("description"),
            severity=event.get("severity", "critical"),
            status=event.get("status", "firing"),
            environment=event.get("environment", "undefined"),
            service=event.get("service"),
            source=["airflow"],
            url=event.get("url"),
            lastReceived=event.get(
                "lastReceived", datetime.now(tz=timezone.utc).isoformat()
            ),
            labels=event.get("labels", {}),
        )
        return alert
