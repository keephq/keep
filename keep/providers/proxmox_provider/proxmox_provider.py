"""
ProxmoxProvider is a class that provides a way to interact with Proxmox VE API
"""

import dataclasses
from datetime import datetime
from typing import List

import pydantic
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class ProxmoxProviderAuthConfig:
    """
    ProxmoxProviderAuthConfig is a class that holds the authentication information for the ProxmoxProvider.
    """

    host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Proxmox Host URL",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    token_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "API Token ID in format user@realm!tokenname",
            "sensitive": False,
        },
    )

    token_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "API Token Secret",
            "sensitive": True,
        },
    )

    verify_ssl: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "sensitive": False,
        },
        default=False,
    )


class ProxmoxProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Proxmox VE"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Infrastructure"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts",
            description="Read alerts from Proxmox VE",
        )
    ]

    SEVERITY_MAP = {
        "offline": AlertSeverity.CRITICAL,
        "degraded": AlertSeverity.HIGH,
        "stopped": AlertSeverity.HIGH,
        "low_space": AlertSeverity.WARNING,
        "zfs_degraded": AlertSeverity.HIGH,
    }

    STATUS_MAP = {
        "offline": AlertStatus.FIRING.value,
        "degraded": AlertStatus.FIRING.value,
        "stopped": AlertStatus.FIRING.value,
        "low_space": AlertStatus.FIRING.value,
        "zfs_degraded": AlertStatus.FIRING.value,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.session = requests.Session()
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _get_auth_headers(self):
        return {
            "Authorization": f"PVEAPIToken={self.authentication_config.token_id}={self.authentication_config.token_secret}"
        }

    def validate_scopes(self):
        """
        Validate that the scopes provided in the config are valid
        """
        try:
            response = self.session.get(
                f"{self.authentication_config.host}/api2/json/version",
                headers=self._get_auth_headers(),
                verify=self.authentication_config.verify_ssl,
            )
            response.raise_for_status()
            return {"alerts": True}
        except Exception:
            return {"alerts": False}

    def validate_config(self):
        self.authentication_config = ProxmoxProviderAuthConfig(
            **self.config.authentication
        )

    def _get_nodes(self):
        try:
            response = self.session.get(
                f"{self.authentication_config.host}/api2/json/nodes",
                headers=self._get_auth_headers(),
                verify=self.authentication_config.verify_ssl,
            )
            response.raise_for_status()
            return response.json()["data"]
        except Exception as e:
            self.logger.error("Error getting nodes from Proxmox: %s", e)
            raise Exception(f"Error getting nodes from Proxmox: {e}")

    def _get_node_status(self, node_name):
        try:
            response = self.session.get(
                f"{self.authentication_config.host}/api2/json/nodes/{node_name}/status",
                headers=self._get_auth_headers(),
                verify=self.authentication_config.verify_ssl,
            )
            response.raise_for_status()
            return response.json()["data"]
        except Exception as e:
            self.logger.error("Error getting node status from Proxmox: %s", e)
            raise Exception(f"Error getting node status from Proxmox: {e}")

    def _get_vms(self):
        vms = []
        nodes = self._get_nodes()
        for node in nodes:
            try:
                response = self.session.get(
                    f"{self.authentication_config.host}/api2/json/nodes/{node['node']}/qemu",
                    headers=self._get_auth_headers(),
                    verify=self.authentication_config.verify_ssl,
                )
                response.raise_for_status()
                node_vms = response.json()["data"]
                vms.extend(node_vms)
            except Exception as e:
                self.logger.error("Error getting VMs from node %s: %s", node["node"], e)
        return vms

    def _get_containers(self):
        containers = []
        nodes = self._get_nodes()
        for node in nodes:
            try:
                response = self.session.get(
                    f"{self.authentication_config.host}/api2/json/nodes/{node['node']}/lxc",
                    headers=self._get_auth_headers(),
                    verify=self.authentication_config.verify_ssl,
                )
                response.raise_for_status()
                node_containers = response.json()["data"]
                containers.extend(node_containers)
            except Exception as e:
                self.logger.error("Error getting containers from node %s: %s", node["node"], e)
        return containers

    def _get_storage(self):
        storage = []
        nodes = self._get_nodes()
        for node in nodes:
            try:
                response = self.session.get(
                    f"{self.authentication_config.host}/api2/json/nodes/{node['node']}/storage",
                    headers=self._get_auth_headers(),
                    verify=self.authentication_config.verify_ssl,
                )
                response.raise_for_status()
                node_storage = response.json()["data"]
                storage.extend(node_storage)
            except Exception as e:
                self.logger.error("Error getting storage from node %s: %s", node["node"], e)
        return storage

    def _get_alerts(self) -> List[AlertDto]:
        alerts = []
        
        # Get node status
        try:
            nodes = self._get_nodes()
            for node in nodes:
                node_status = self._get_node_status(node["node"])
                if node_status.get("status") == "offline":
                    alert = AlertDto(
                        id=f"node_offline_{node['node']}",
                        name=f"Node {node['node']} is offline",
                        description=f"Node {node['node']} is currently offline",
                        status=AlertStatus.FIRING.value,
                        severity=AlertSeverity.CRITICAL,
                        lastReceived=datetime.now().isoformat(),
                        source=["proxmox"],
                    )
                    alerts.append(alert)
                elif node_status.get("status") == "degraded":
                    alert = AlertDto(
                        id=f"node_degraded_{node['node']}",
                        name=f"Node {node['node']} is degraded",
                        description=f"Node {node['node']} is currently degraded",
                        status=AlertStatus.FIRING.value,
                        severity=AlertSeverity.HIGH,
                        lastReceived=datetime.now().isoformat(),
                        source=["proxmox"],
                    )
                    alerts.append(alert)
        except Exception as e:
            self.logger.error("Error getting node alerts from Proxmox: %s", e)

        # Get VM status
        try:
            vms = self._get_vms()
            for vm in vms:
                if vm.get("status") == "stopped":
                    alert = AlertDto(
                        id=f"vm_stopped_{vm['vmid']}",
                        name=f"VM {vm['name']} ({vm['vmid']}) is stopped",
                        description=f"VM {vm['name']} ({vm['vmid']}) is currently stopped unexpectedly",
                        status=AlertStatus.FIRING.value,
                        severity=AlertSeverity.HIGH,
                        lastReceived=datetime.now().isoformat(),
                        source=["proxmox"],
                    )
                    alerts.append(alert)
        except Exception as e:
            self.logger.error("Error getting VM alerts from Proxmox: %s", e)

        # Get container status
        try:
            containers = self._get_containers()
            for container in containers:
                if container.get("status") == "stopped":
                    alert = AlertDto(
                        id=f"container_stopped_{container['vmid']}",
                        name=f"Container {container['name']} ({container['vmid']}) is stopped",
                        description=f"Container {container['name']} ({container['vmid']}) is currently stopped unexpectedly",
                        status=AlertStatus.FIRING.value,
                        severity=AlertSeverity.HIGH,
                        lastReceived=datetime.now().isoformat(),
                        source=["proxmox"],
                    )
                    alerts.append(alert)
        except Exception as e:
            self.logger.error("Error getting container alerts from Proxmox: %s", e)

        # Get storage status
        try:
            storage = self._get_storage()
            for storage_item in storage:
                if storage_item.get("type") == "zfs" and storage_item.get("status") == "degraded":
                    alert = AlertDto(
                        id=f"storage_zfs_degraded_{storage_item['storage']}",
                        name=f"Storage pool {storage_item['storage']} is degraded",
                        description=f"Storage pool {storage_item['storage']} is currently degraded",
                        status=AlertStatus.FIRING.value,
                        severity=AlertSeverity.HIGH,
                        lastReceived=datetime.now().isoformat(),
                        source=["proxmox"],
                    )
                    alerts.append(alert)
                elif storage_item.get("type") in ["zfspool", "lvmthin", "dir", "lvm"]:
                    # Check if used/total ratio > 0.9 for all storage types
                    used = storage_item.get("used", 0)
                    total = storage_item.get("total", 0)
                    if total > 0 and (used / total) > 0.9:
                        alert = AlertDto(
                            id=f"storage_low_space_{storage_item['storage']}",
                            name=f"Storage pool {storage_item['storage']} is running low on space",
                            description=f"Storage pool {storage_item['storage']} is running low on space",
                            status=AlertStatus.FIRING.value,
                            severity=AlertSeverity.WARNING,
                            lastReceived=datetime.now().isoformat(),
                            source=["proxmox"],
                        )
                        alerts.append(alert)
        except Exception as e:
            self.logger.error("Error getting storage alerts from Proxmox: %s", e)

        return alerts

    @classmethod
    def _format_alert(
        cls, event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # This method is not used in this provider as we fetch alerts directly
        # but it's required by the base class
        return AlertDto(
            id=event.get("id"),
            name=event.get("name", "unknown"),
            description=event.get("description", ""),
            status=event.get("status", AlertStatus.FIRING.value),
            severity=event.get("severity", AlertSeverity.INFO),
            lastReceived=event.get("lastReceived"),
            source=["proxmox"],
        )

    def dispose(self):
        self.session.close()


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    proxmox_host = os.environ.get("PROXMOX_HOST")
    proxmox_token_id = os.environ.get("PROXMOX_TOKEN_ID")
    proxmox_token_secret = os.environ.get("PROXMOX_TOKEN_SECRET")

    if proxmox_host is None:
        raise Exception("PROXMOX_HOST is required")
    if proxmox_token_id is None:
        raise Exception("PROXMOX_TOKEN_ID is required")
    if proxmox_token_secret is None:
        raise Exception("PROXMOX_TOKEN_SECRET is required")

    config = ProviderConfig(
        description="Proxmox Provider",
        authentication={
            "host": proxmox_host,
            "token_id": proxmox_token_id,
            "token_secret": proxmox_token_secret,
            "verify_ssl": False,
        },
    )

    provider = ProxmoxProvider(
        context_manager=context_manager,
        provider_id="proxmox",
        config=config,
    )

    alerts = provider.get_alerts()
    print(alerts)
    provider.dispose()
