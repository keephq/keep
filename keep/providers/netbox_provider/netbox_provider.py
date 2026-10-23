"""
NetBox combines IP address management (IPAM) and datacenter infrastructure management (DCIM) with powerful APIs and extensions, serving as the ideal "source of truth" for network automation. Thousands of organizations worldwide rely on NetBox for their infrastructure.
"""

import dataclasses
import uuid

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider, BaseTopologyProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NetboxProviderAuthConfig:
    """
    NetboxProviderAuthConfig is a class that holds the authentication information for the NetboxProvider.

    All fields are optional: NetBox can be used webhook-only (alerts pushed to Keep),
    and the API access is only needed to pull the DCIM topology.
    """

    url: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "NetBox instance URL",
            "hint": "e.g. https://netbox.example.com, needed only for topology pulling",
            "sensitive": False,
        },
    )

    api_token: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "NetBox API token",
            "hint": "A read-only token is enough, needed only for topology pulling",
            "sensitive": True,
        },
    )

    verify: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
            "type": "switch",
        },
    )

    group_racks_as_applications: bool = dataclasses.field(
        default=False,
        metadata={
            "required": False,
            "description": "Group devices of the same rack into an application",
            "hint": "Lets topology correlation group alerts of devices sharing a rack",
            "sensitive": False,
            "type": "switch",
        },
    )

    max_devices: int = dataclasses.field(
        default=5000,
        metadata={
            "required": False,
            "description": "Maximum number of devices to pull",
            "sensitive": False,
        },
    )


def _termination_device_names(cable: dict, side: str) -> set[str]:
    # NetBox >= 3.3 exposes a list of terminations per side, older versions a single object
    terminations = cable.get(f"{side}_terminations")
    if terminations is None:
        single = cable.get(f"termination_{side}")
        terminations = [{"object": single}] if single else []
    names = set()
    for termination in terminations:
        device = (termination.get("object") or {}).get("device") or {}
        if device.get("name"):
            names.add(device["name"])
    return names


def _rack_application_id(application_namespace: str, rack_id) -> uuid.UUID:
    # stable per tenant/provider/rack, so a re-pull updates the application in place
    namespace_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, "keephq.dev")
    return uuid.uuid5(namespace_uuid, f"{application_namespace}/netbox-rack/{rack_id}")


def build_topology_services(
    devices: list[dict],
    cables: list[dict],
    source_provider_id: str,
    application_namespace: str,
    group_racks_as_applications: bool = False,
) -> list[TopologyServiceInDto]:
    """Map NetBox DCIM devices and cables to Keep topology services.

    Devices become services keyed by their name (the attribute monitoring tools
    report alerts with), cables between two known devices become dependencies,
    and optionally the devices of a rack are grouped into an application.
    """
    services: dict[str, TopologyServiceInDto] = {}

    for device in devices:
        name = device.get("name") or f"device-{device.get('id')}"
        primary_ip = (device.get("primary_ip") or {}).get("address") or ""
        # "role" since NetBox v4, "device_role" before
        role = device.get("role") or device.get("device_role") or {}
        device_type = device.get("device_type") or {}
        rack = device.get("rack") or {}

        application_relations = None
        if group_racks_as_applications and rack.get("id") is not None:
            rack_name = rack.get("name") or f"rack-{rack['id']}"
            application_relations = {
                _rack_application_id(
                    application_namespace, rack["id"]
                ): f"Rack {rack_name}"
            }

        services[name] = TopologyServiceInDto(
            source_provider_id=source_provider_id,
            service=name,
            display_name=name,
            description=device.get("description") or None,
            ip_address=primary_ip.split("/")[0] or None,
            category=role.get("name"),
            manufacturer=(device_type.get("manufacturer") or {}).get("name"),
            namespace=(device.get("site") or {}).get("name"),
            tags=[tag["name"] for tag in device.get("tags") or [] if tag.get("name")],
            application_relations=application_relations,
        )

    for cable in cables:
        a_names = _termination_device_names(cable, "a")
        b_names = _termination_device_names(cable, "b")
        for a_name in a_names:
            for b_name in b_names:
                if a_name == b_name:
                    continue
                if a_name in services and b_name in services:
                    services[a_name].dependencies[b_name] = "cable"

    return list(services.values())


class NetboxProvider(BaseTopologyProvider):
    """
    Get alerts and topology from NetBox into Keep.
    """

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
  To send alerts from NetBox to Keep, Use the following webhook url to configure NetBox send alerts to Keep:

  1. In NetBox, go to Webhooks under Operations.
  2. Create a new webhook with URL as {keep_webhook_api_url} and request method as POST.
  3. Disable SSL verification.
  4. Add 'X-API-KEY' as the request header with the value as {api_key}.
  5. Save the webhook.
  6. Go to Event Rules and create a new rule and select the webhook created in step 2 to receive alerts.
  """

    PROVIDER_DISPLAY_NAME = "NetBox"
    PROVIDER_TAGS = ["alert", "topology"]
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(name="authenticated", description="User is authenticated"),
    ]

    REQUEST_TIMEOUT = 10

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates required configuration for NetBox's provider.
        """
        self.authentication_config = NetboxProviderAuthConfig(
            **(self.config.authentication or {})
        )

    @property
    def _api_configured(self) -> bool:
        return bool(
            self.authentication_config.url and self.authentication_config.api_token
        )

    def _get(self, path: str, params: dict | None = None) -> dict:
        url = self.authentication_config.url.rstrip("/") + path
        response = requests.get(
            url,
            headers={"Authorization": f"Token {self.authentication_config.api_token}"},
            params=params,
            verify=self.authentication_config.verify,
            timeout=self.REQUEST_TIMEOUT,
        )
        if not response.ok:
            raise ProviderException(
                f"Failed to fetch {path} from NetBox: {response.status_code} {response.text}"
            )
        return response.json()

    def _get_paginated(self, path: str, params: dict | None = None) -> list[dict]:
        limit = self.authentication_config.max_devices
        page_size = min(limit, 1000)
        results: list[dict] = []
        offset = 0
        while True:
            data = self._get(
                path, params={**(params or {}), "limit": page_size, "offset": offset}
            )
            results.extend(data.get("results") or [])
            if len(results) >= limit:
                if data.get("next"):
                    self.logger.warning(
                        "NetBox returned more than max_devices objects, truncating",
                        extra={"path": path, "max_devices": limit},
                    )
                return results[:limit]
            if not data.get("next"):
                return results
            offset += page_size

    def validate_scopes(self) -> dict[str, bool | str]:
        # webhook-only installs have no API access to validate
        if not self._api_configured:
            return {"authenticated": True}
        try:
            self._get("/api/status/")
            # the token also needs DCIM read access to pull the topology
            self._get("/api/dcim/devices/", params={"limit": 1})
            return {"authenticated": True}
        except Exception as e:
            return {"authenticated": f"Error validating scopes: {e}"}

    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        if not self._api_configured:
            # webhook-only install, nothing to pull
            self.logger.debug(
                "NetBox API access is not configured, skipping topology pull"
            )
            return [], {}

        self.logger.info("Pulling topology from NetBox")
        devices = self._get_paginated(
            "/api/dcim/devices/", params={"exclude": "config_context"}
        )
        cables = self._get_paginated("/api/dcim/cables/")
        services = build_topology_services(
            devices,
            cables,
            source_provider_id=self.provider_id,
            application_namespace=f"{self.context_manager.tenant_id}/{self.provider_id}",
            group_racks_as_applications=self.authentication_config.group_racks_as_applications,
        )
        self.logger.info(
            "Pulled topology from NetBox",
            extra={"devices": len(devices), "cables": len(cables)},
        )
        return services, {}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:

        data = event.get("data", {})
        snapshots = event.get("snapshots", {})

        alert = AlertDto(
            name=data.get("name", "Could not fetch name"),
            lastReceived=event.get("timestamp"),
            startedAt=data.get("created"),
            model=event.get("model", "Could not fetch model"),
            username=event.get("username", "Could not fetch username"),
            id=event.get("request_id"),
            data=data,
            description=event.get("event", "Could not fetch event"),
            snapshots=snapshots,
            source=["netbox"],
        )

        return alert


if __name__ == "__main__":
    pass
