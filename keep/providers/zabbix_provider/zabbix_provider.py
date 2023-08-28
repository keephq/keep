"""
Zabbix Provider is a class that allows to ingest/digest data from Zabbix.
"""
import dataclasses
import datetime
import json
import os
import random

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class ZabbixProviderAuthConfig:
    """
    Zabbix authentication configuration.
    """

    zabbix_frontend_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zabbix Frontend URL",
            "hint": "https://zabbix.example.com",
            "sensitive": False,
        }
    )
    auth_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zabbix Auth Token",
            "hint": "Users -> Api tokens",
            "sensitive": True,
        }
    )


class ZabbixProvider(BaseProvider):
    """
    Zabbix provider class.
    """

    KEEP_ZABBIX_WEBHOOK_INTEGRATION_NAME = "keep"  # keep-zabbix
    KEEP_ZABBIX_WEBHOOK_SCRIPT_FILENAME = (
        "zabbix_provider_script.js"  # zabbix mediatype script file
    )
    KEEP_ZABBIX_WEBHOOK_MEDIATYPE_TYPE = 4

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Zabbix provider.

        """
        self.authentication_config = ZabbixProviderAuthConfig(
            **self.config.authentication
        )

    def __send_request(self, method: str, params: dict = None):
        """
        Send a request to Zabbix API.

        Args:
            method (str): The method to call.
            params (dict): The parameters to send.

        Returns:
            dict: The response from Zabbix API.
        """
        url = f"{self.authentication_config.zabbix_frontend_url}/api_jsonrpc.php"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.authentication_config.auth_token}",
        }
        data = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": random.randint(1000, 2000),
        }

        # zabbix < 6.4 compatibility
        data["auth"] = f"{self.authentication_config.auth_token}"
        self.logger.info(f"Sending data: {data}")

        response = requests.post(url, json=data, headers=headers)

        response.raise_for_status()
        response_json = response.json()
        if "error" in response_json:
            raise Exception(response_json["error"])
        return response_json

    def get_alerts(self) -> list[AlertDto]:
        formatted_alerts = []
        return formatted_alerts

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        # Copied from https://git.zabbix.com/projects/ZBX/repos/zabbix/browse/templates/media/ilert/media_ilert.yaml?at=release%2F6.4
        # Based on @SomeAverageDev hints and suggestions ;) Thanks!
        # TODO: this can be done once when loading the provider file
        self.logger.info("Reading webhook JS script file")
        __location__ = os.path.realpath(
            os.path.join(os.getcwd(), os.path.dirname(__file__))
        )

        with open(
            os.path.join(
                __location__, ZabbixProvider.KEEP_ZABBIX_WEBHOOK_SCRIPT_FILENAME
            )
        ) as f:
            script = f.read()

        self.logger.info("Creating or updating webhook")
        mediatype_name = f"{ZabbixProvider.KEEP_ZABBIX_WEBHOOK_INTEGRATION_NAME}"  # -{tenant_id.replace('-', '')}

        self.logger.info("Getting existing media types")
        existing_mediatypes = self.__send_request(
            "mediatype.get",
            {
                "output": ["mediatypeid", "name"],
                "filter": {"type": [ZabbixProvider.KEEP_ZABBIX_WEBHOOK_MEDIATYPE_TYPE]},
            },
        )

        mediatype_description = "Please refer to https://docs.keephq.dev/platform/core/providers/documentation/zabbix-provider or https://platform.keephq.dev/."

        self.logger.info("Got existing media types")
        mediatype_list = [
            mt
            for mt in existing_mediatypes.get("result", [])
            if mt["name"] == mediatype_name
        ]

        if mediatype_list:
            existing_mediatype = mediatype_list[0]
            self.logger.info("Updating existing media type")
            self.__send_request(
                "mediatype.update",
                {
                    "mediatypeid": str(existing_mediatype["mediatypeid"]),
                    "script": script,
                    "status": "0",
                    "description": mediatype_description,
                },
            )
            self.logger.info("Updated existing media type")
        else:
            self.logger.info("Creating new media type")
            params = {
                "name": mediatype_name,
                "type": f"{ZabbixProvider.KEEP_ZABBIX_WEBHOOK_MEDIATYPE_TYPE}",  # webhook
                "parameters": [
                    {"name": "keepApiKey", "value": api_key},
                    {"name": "keepApiUrl", "value": keep_api_url},
                    {"name": "id", "value": "{EVENT.ID}"},
                    {"name": "triggerId", "value": "{TRIGGER.ID}"},
                    {"name": "lastReceived", "value": "{EVENT.DATE} {EVENT.TIME}"},
                    {"name": "message", "value": "{ALERT.MESSAGE}"},
                    {"name": "name", "value": "{EVENT.NAME}"},
                    {"name": "service", "value": "{HOST.HOST}"},
                    {"name": "severity", "value": "{TRIGGER.SEVERITY}"},
                    {"name": "status", "value": "{TRIGGER.STATUS}"},
                    {"name": "ALERT.SUBJECT", "value": "{ALERT.SUBJECT}"},
                    {"name": "EVENT.SEVERITY", "value": "{EVENT.SEVERITY}"},
                    {"name": "EVENT.TAGS", "value": "{EVENT.TAGS}"},
                    {"name": "EVENT.TIME", "value": "{EVENT.TIME}"},
                    {"name": "EVENT.VALUE", "value": "{EVENT.VALUE}"},
                    {"name": "HOST.IP", "value": "{HOST.IP}"},
                    {"name": "HOST.NAME", "value": "{HOST.NAME}"},
                    {"name": "description", "value": "{TRIGGER.DESCRIPTION}"},
                    {"name": "ZABBIX.URL", "value": "{$ZABBIX.URL}"},
                ],
                "script": script,
                "process_tags": 1,
                "show_event_menu": 0,
                "description": mediatype_description,
                "message_templates": [
                    {
                        "eventsource": 0,
                        "recovery": 0,
                        "subject": "Problem: {EVENT.NAME}",
                        "message": "Problem started at {EVENT.TIME} on {EVENT.DATE}\nProblem name: {EVENT.NAME}\nHost: {HOST.NAME}\nSeverity: {EVENT.SEVERITY}\nOperational data: {EVENT.OPDATA}\nOriginal problem ID: {EVENT.ID}\n{TRIGGER.URL}\n",
                    },
                    {
                        "eventsource": 0,
                        "recovery": 2,
                        "subject": "Updated problem in {EVENT.AGE}: {EVENT.NAME}",
                        "message": "{USER.FULLNAME} {EVENT.UPDATE.ACTION} problem at {EVENT.UPDATE.DATE} {EVENT.UPDATE.TIME}.\n{EVENT.UPDATE.MESSAGE}\n\nCurrent problem status is {EVENT.STATUS}, age is {EVENT.AGE}, acknowledged: {EVENT.ACK.STATUS}.\n",
                    },
                    {
                        "eventsource": 0,
                        "recovery": 1,
                        "subject": "Resolved in {EVENT.DURATION}: {EVENT.NAME}",
                        "message": "Problem has been resolved at {EVENT.RECOVERY.TIME} on {EVENT.RECOVERY.DATE}\nProblem name: {EVENT.NAME}\nProblem duration: {EVENT.DURATION}\nHost: {HOST.NAME}\nSeverity: {EVENT.SEVERITY}\nOriginal problem ID: {EVENT.ID}\n{TRIGGER.URL}\n",
                    },
                ],
            }
            response_json = self.__send_request("mediatype.create", params)
            self.__send_request(
                "mediatype.update",
                {
                    "mediatypeid": str(
                        response_json.get("result", {}).get("mediatypeids", [])[0]
                    ),
                    "status": "0",
                },
            )
            self.logger.info("Created media type")

    @staticmethod
    def __get_priorty(priority):
        if priority == "disaster":
            return "critical"
        elif priority == "high":
            return "high"
        elif priority == "average":
            return "medium"
        else:
            return "low"

    @staticmethod
    def format_alert(event: dict) -> AlertDto:
        environment = "unknown"
        tags = event.get("tags", {})
        if isinstance(tags, dict):
            environment = tags.get("environment", "unknown")
        severity = ZabbixProvider.__get_priorty(event.pop("severity", "").lower())
        event_id = event.get("id")
        trigger_id = event.get("triggerId")
        zabbix_url = event.pop("ZABBIX.URL", None)
        url = None
        if event_id and trigger_id and zabbix_url:
            url = (
                f"{zabbix_url}/tr_events.php?triggerid={trigger_id}&eventid={event_id}"
            )
        return AlertDto(
            **event,
            environment=environment,
            pushed=True,
            source=["zabbix"],
            severity=severity,
            url=url,
        )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    auth_token = os.environ.get("ZABBIX_AUTH_TOKEN")

    provider_config = {
        "authentication": {
            "auth_token": auth_token,
            "zabbix_frontend_url": "http://localhost",
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="zabbix",
        provider_type="zabbix",
        provider_config=provider_config,
    )
    provider.setup_webhook(
        "e1faa321-35df-486b-8fa8-3601ee714011", "http://localhost:8080", "abc"
    )
