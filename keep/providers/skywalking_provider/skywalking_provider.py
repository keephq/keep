\"\"\"
SkywalkingProvider is a class that provides a way to read data from Apache SkyWalking.
\"\"\"

import dataclasses
import datetime
import os

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


@pydantic.dataclasses.dataclass
class SkywalkingProviderAuthConfig:
    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SkyWalking OAP server GraphQL URL",
            "hint": "http://skywalking-oap:12800/graphql",
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "description": "SkyWalking username",
            "sensitive": False,
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "description": "SkyWalking password",
            "sensitive": True,
        },
        default="",
    )


class SkywalkingProvider(BaseProvider, ProviderHealthMixin):
    \"\"\"Get alerts and metrics from Apache SkyWalking into Keep.\"\"\"

    PROVIDER_DISPLAY_NAME = "Apache SkyWalking"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "data"]

    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "ERROR": AlertSeverity.HIGH,
        "WARNING": AlertSeverity.WARNING,
        "INFO": AlertSeverity.INFO,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity", description="Connectivity Test", mandatory=True
        )
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="query_layers",
            func_name="query_layers",
            description="Query all available layers from SkyWalking",
            type="view",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        \"\"\"
        Validates required configuration for SkyWalking's provider.
        \"\"\"
        self.authentication_config = SkywalkingProviderAuthConfig(
            **self.config.authentication
        )

    def _query_graphql(self, query: str, variables: dict = None):
        auth = None
        if self.authentication_config.username and self.authentication_config.password:
            auth = (
                self.authentication_config.username,
                self.authentication_config.password,
            )

        response = requests.post(
            str(self.authentication_config.url),
            json={"query": query, "variables": variables},
            auth=auth,
            verify=False,
        )
        response.raise_for_status()
        result = response.json()
        if "errors" in result:
            raise Exception(f"SkyWalking GraphQL error: {result['errors']}")
        return result.get("data", {})

    def _get_alerts(self) -> list[AlertDto]:
        # SkyWalking uses 'Duration' input for time ranges
        now = datetime.datetime.now()
        # Default to last 15 minutes of alarms
        start = (now - datetime.timedelta(minutes=15)).strftime("%Y-%m-%d %H%M")
        end = now.strftime("%Y-%m-%d %H%M")

        query = \"\"\"
        query getAlarms($duration: Duration!) {
          getAlarm(duration: $duration, paging: { pageNum: 1, pageSize: 100 }) {
            msgs {
              key
              message
              startTime
              scope
              tags {
                key
                value
              }
            }
          }
        }
        \"\"\"
        variables = {
            "duration": {
                "start": start,
                "end": end,
                "step": "MINUTE",
            }
        }
        data = self._query_graphql(query, variables)
        alarms = data.get("getAlarm", {}).get("msgs", [])
        return self._format_alert(alarms)

    @staticmethod
    def _format_alert(
        event: dict | list[dict], provider_instance: "BaseProvider" = None
    ) -> list[AlertDto]:
        if isinstance(event, list):
            # If it's already a list of dicts from GraphQL
            alarms = event
        else:
            # If it's a wrapped event or single dict
            alarms = event.get("msgs", [event]) if "msgs" in event else [event]
        
        # Support simulate_alert format if wrapped
        if not alarms and "event" in event:
            alarms = [event["event"]]

        alert_dtos = []
        for alarm in alarms:
            if not isinstance(alarm, dict):
                continue
            alarm_id = alarm.get("key")
            message = alarm.get("message")
            start_time = alarm.get("startTime")  # Milliseconds timestamp
            tags_list = alarm.get("tags", [])
            tags = {tag["key"]: tag["value"] for tag in tags_list if isinstance(tag, dict)}
            
            severity_str = tags.get("severity", "INFO").upper()
            severity = SkywalkingProvider.SEVERITIES_MAP.get(severity_str, AlertSeverity.INFO)

            alert_dtos.append(
                AlertDto(
                    id=alarm_id,
                    name=f"SkyWalking Alarm: {alarm.get('scope', 'Global')}",
                    description=message,
                    status=AlertStatus.FIRING,
                    severity=severity,
                    lastReceived=datetime.datetime.fromtimestamp(
                        int(start_time) / 1000, tz=datetime.timezone.utc
                    ).isoformat() if start_time else datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
                    source=["skywalking"],
                    labels=tags,
                    payload=alarm,
                )
            )
        return alert_dtos

    def _query(self, query: str, **kwargs) -> list[dict]:
        \"\"\"
        Execute a custom GraphQL query against SkyWalking.
        \"\"\"
        return self._query_graphql(query, kwargs.get("variables"))

    def query_layers(self) -> list[str]:
        \"\"\"
        List all available layers in SkyWalking.
        \"\"\"
        query = \"{ listLayers }\"
        data = self._query_graphql(query)
        return data.get("listLayers", [])

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        \"\"\"Mock a SkyWalking alarm.\"\"\"
        import random
        import time

        from keep.providers.skywalking_provider.alerts_mock import ALERTS

        alert_type = "SkyWalkingAlarm"
        alert_payload = ALERTS[alert_type]["payload"].copy()
        alert_parameters = ALERTS[alert_type].get("parameters", {})

        for parameter, parameter_options in alert_parameters.items():
            alert_payload[parameter] = random.choice(parameter_options)

        alert_payload["key"] = f"mock-{random.randint(1000, 9999)}"
        alert_payload["startTime"] = int(time.time() * 1000)

        return alert_payload

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {"connectivity": True}
        try:
            # Simple metadata query to test connectivity
            query = "{ listLayers }"
            self._query_graphql(query)
        except Exception as e:
            validated_scopes["connectivity"] = str(e)
        return validated_scopes

    def dispose(self):
        pass


if __name__ == "__main__":
    # Test script
    config = ProviderConfig(
        authentication={
            "url": os.environ.get("SKYWALKING_URL", "http://localhost:12800/graphql")
        }
    )
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = SkywalkingProvider(context_manager, "skywalking-test", config)
    provider.validate_config()
    print(provider.validate_scopes())
