"""
ManageEngineProvider integrates Keep with ManageEngine ServiceDesk Plus.
Supports pulling open requests/incidents from the ServiceDesk Plus REST API and
creating new requests from Keep alert workflows.
"""

import dataclasses
import datetime
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class ManageEngineProviderAuthConfig:
    """
    ManageEngineProviderAuthConfig holds credentials for ManageEngine ServiceDesk Plus.
    """

    server_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": (
                "ServiceDesk Plus server URL "
                "(e.g. https://sdpondemand.manageengine.com or http://sdp-server:8080)"
            ),
            "sensitive": False,
            "hint": "Your ServiceDesk Plus URL, e.g. https://sdpondemand.manageengine.com",
        },
    )

    technician_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Technician API Key (Admin → General → API → API Key)",
            "sensitive": True,
        },
    )

    portal_name: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Portal name for cloud instances (leave blank for on-premise)",
            "sensitive": False,
            "hint": "Required for cloud (SDP On-Demand) only, e.g. 'mycompany'",
        },
    )


class ManageEngineProvider(BaseProvider):
    """Pull requests/incidents from ManageEngine ServiceDesk Plus and create new tickets."""

    PROVIDER_DISPLAY_NAME = "ManageEngine ServiceDesk Plus"
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_CATEGORY = ["ITSM"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_requests",
            description="Read requests/incidents from ServiceDesk Plus",
            mandatory=True,
        ),
        ProviderScope(
            name="create_request",
            description="Create new requests in ServiceDesk Plus",
            mandatory=False,
        ),
    ]

    # SDP priority → Keep AlertSeverity
    SEVERITY_MAP = {
        "High": AlertSeverity.HIGH,
        "Medium": AlertSeverity.WARNING,
        "Low": AlertSeverity.LOW,
        "Urgent": AlertSeverity.CRITICAL,
        "Normal": AlertSeverity.INFO,
        "1": AlertSeverity.CRITICAL,  # Urgent
        "2": AlertSeverity.HIGH,      # High
        "3": AlertSeverity.WARNING,   # Medium
        "4": AlertSeverity.LOW,       # Low
    }

    # SDP status → Keep AlertStatus
    STATUS_MAP = {
        "Open": AlertStatus.FIRING,
        "In Progress": AlertStatus.ACKNOWLEDGED,
        "On Hold": AlertStatus.ACKNOWLEDGED,
        "Resolved": AlertStatus.RESOLVED,
        "Closed": AlertStatus.RESOLVED,
    }

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send ManageEngine ServiceDesk Plus alerts to Keep, configure a Notification Rule:

1. Log in to ServiceDesk Plus as Administrator.
2. Go to **Admin** → **Helpdesk Customizer** → **Notification Rules**.
3. Click **Add Notification Rule** or edit an existing rule.
4. Under **Notify via**, select **Webhook**.
5. Set the webhook URL to `{keep_webhook_api_url}`.
6. Add a custom header: `X-API-KEY` = `{api_key}`.
7. Set the body to send request details in JSON format.
8. Save and enable the rule.

Alternatively, use **Business Rules** under **Admin → Business Rules** to trigger webhooks on request creation or update.
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ManageEngineProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _base_url(self) -> str:
        url = self.authentication_config.server_url.rstrip("/")
        if self.authentication_config.portal_name:
            return f"{url}/app/{self.authentication_config.portal_name}/api/v3"
        return f"{url}/api/v3"

    def _get_params(self) -> dict:
        return {"TECHNICIAN_KEY": self.authentication_config.technician_key}

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            import json

            list_info = {
                "row_count": 1,
                "start_index": 0,
                "sort_field": "id",
                "sort_order": "asc",
                "filter_by": {"name": "status.name", "value": "Open"},
            }
            response = requests.get(
                f"{self._base_url()}/requests",
                params={
                    **self._get_params(),
                    "input_data": json.dumps({"list_info": list_info}),
                },
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_requests": True, "create_request": True}
            return {
                "read_requests": f"HTTP {response.status_code}: {response.text[:200]}",
                "create_request": f"HTTP {response.status_code}: {response.text[:200]}",
            }
        except Exception as e:
            self.logger.error("Error validating ManageEngine ServiceDesk Plus scopes: %s", e)
            return {"read_requests": str(e), "create_request": str(e)}

    def _get_alerts(self) -> List[AlertDto]:
        import json

        alerts = []
        try:
            self.logger.info("Pulling open requests from ManageEngine ServiceDesk Plus")
            start_index = 0
            row_count = 100

            while True:
                list_info = {
                    "row_count": row_count,
                    "start_index": start_index,
                    "sort_field": "id",
                    "sort_order": "desc",
                    "filter_by": {
                        "name": "status.name",
                        "value": ["Open", "In Progress", "On Hold"],
                        "condition": "is",
                        "logical_operator": "OR",
                    },
                }
                response = requests.get(
                    f"{self._base_url()}/requests",
                    params={
                        **self._get_params(),
                        "input_data": json.dumps({"list_info": list_info}),
                    },
                    timeout=30,
                )
                if not response.ok:
                    self.logger.error(
                        "Failed to fetch ServiceDesk Plus requests: %s", response.text
                    )
                    break

                data = response.json()
                requests_list = data.get("requests", [])
                if not requests_list:
                    break

                for item in requests_list:
                    alerts.append(self._item_to_alert_dto(item))

                list_info_resp = data.get("list_info", {})
                has_more = list_info_resp.get("has_more_rows", False)
                if not has_more:
                    break
                start_index += row_count

        except Exception as e:
            self.logger.error("Error pulling ManageEngine ServiceDesk Plus requests: %s", e)
        return alerts

    def _item_to_alert_dto(self, item: dict) -> AlertDto:
        request_id = str(item.get("id", ""))
        subject = item.get("subject", f"Request #{request_id}")
        description = item.get("description", "")
        status = item.get("status", {}).get("name", "Open")
        priority = item.get("priority", {}).get("name", "Medium")
        created_time = item.get("created_time", {}).get("display_value")
        last_updated = item.get("last_updated_time", {}).get("display_value")
        last_received = last_updated or created_time or datetime.datetime.utcnow().isoformat()

        requester = item.get("requester", {}).get("name", "")
        technician = item.get("technician", {}).get("name", "")
        category = item.get("category", {}).get("name", "")
        request_type = item.get("request_type", {}).get("name", "")

        server_url = self.authentication_config.server_url.rstrip("/")
        url = f"{server_url}/WorkOrder.do?woMode=viewWO&woID={request_id}"

        return AlertDto(
            id=request_id,
            name=subject,
            description=description,
            severity=self.SEVERITY_MAP.get(priority, AlertSeverity.WARNING),
            status=self.STATUS_MAP.get(status, AlertStatus.FIRING),
            lastReceived=last_received,
            startedAt=created_time,
            url=url,
            source=["manageengine"],
            labels={
                "status": status,
                "priority": priority,
                "requester": requester,
                "technician": technician,
                "category": category,
                "request_type": request_type,
            },
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a ManageEngine ServiceDesk Plus webhook/notification payload into an AlertDto.

        SDP webhook payloads can vary based on configuration. Common fields include:
        - WorkOrderId / id
        - Subject / subject
        - Status / status
        - Priority / priority
        - Description / description
        """
        # Support both flat and nested payload shapes
        request_id = str(
            event.get("WorkOrderId") or event.get("id") or event.get("request_id", "")
        )
        subject = (
            event.get("Subject")
            or event.get("subject")
            or event.get("name")
            or f"ServiceDesk Request #{request_id}"
        )
        description = event.get("Description") or event.get("description", "")
        status = event.get("Status") or event.get("status", {})
        if isinstance(status, dict):
            status = status.get("name", "Open")
        priority = event.get("Priority") or event.get("priority", {})
        if isinstance(priority, dict):
            priority = priority.get("name", "Medium")

        created_time = event.get("created_time") or event.get("CreatedTime")
        last_received = created_time or datetime.datetime.utcnow().isoformat()

        return AlertDto(
            id=request_id,
            name=subject,
            description=description,
            severity=ManageEngineProvider.SEVERITY_MAP.get(priority, AlertSeverity.WARNING),
            status=ManageEngineProvider.STATUS_MAP.get(status, AlertStatus.FIRING),
            lastReceived=last_received,
            startedAt=created_time,
            url=event.get("url", ""),
            source=["manageengine"],
            labels={
                "status": status,
                "priority": priority,
                "category": event.get("Category") or event.get("category", ""),
                "request_type": event.get("RequestType") or event.get("request_type", ""),
                "technician": event.get("Technician") or event.get("technician", ""),
            },
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    server_url = os.environ.get(
        "MANAGEENGINE_URL", "https://sdpondemand.manageengine.com"
    )
    technician_key = os.environ.get("MANAGEENGINE_TECHNICIAN_KEY", "")
    portal_name = os.environ.get("MANAGEENGINE_PORTAL_NAME", None)

    if not technician_key:
        raise Exception("MANAGEENGINE_TECHNICIAN_KEY is not set")

    config = ProviderConfig(
        description="ManageEngine ServiceDesk Plus Provider",
        authentication={
            "server_url": server_url,
            "technician_key": technician_key,
            "portal_name": portal_name,
        },
    )

    provider = ManageEngineProvider(
        context_manager,
        provider_id="manageengine-test",
        config=config,
    )

    requests_list = provider._get_alerts()
    print(f"Found {len(requests_list)} open requests")
    for r in requests_list:
        print(r)
