"""
Zabbix Provider is a class that allows to ingest/digest data from Zabbix.
"""
import dataclasses
import os
import random

import pydantic
import requests

from keep.api.models.alert import AlertDto
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

    KEEP_ZABBIX_WEBHOOK_INTEGRATION_NAME = "kz"  # keep-zabbix

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

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
        self.logger.info("Creating or updating webhook")
        name = f"{ZabbixProvider.KEEP_ZABBIX_WEBHOOK_INTEGRATION_NAME}-{tenant_id.replace('-', '')}"
        script = "try {\r\n    var result = { tags: {} },\r\n        params = JSON.parse(value),\r\n        req = new HttpRequest(),\r\n        resp = '';\r\n\r\n    if (typeof params.HTTPProxy === 'string' && params.HTTPProxy.trim() !== '') {\r\n        req.setProxy(params.HTTPProxy);\r\n    }\r\n\r\n    var incidentKey = \"zabbix-\" + params['EVENT.ID'];\r\n\r\n    req.addHeader('Accept: application/json');\r\n    req.addHeader('Content-Type: application/json');\r\n    req.addHeader('X-API-KEY: %%API_KEY%%');\r\n\r\n    Zabbix.log(4, '[Keep Webhook] Sending request:' + JSON.stringify(params));\r\n    resp = req.post('%%KEEP_API_URL%%', JSON.stringify(params));\r\n    Zabbix.log(4, '[Keep Webhook] Receiving response:' + resp);\r\n\r\n    if (req.getStatus() != 200) {\r\n        throw 'Response code not 200'; }\r\nelse\r\n {\r\n          return JSON.stringify(result);\r\n    }\r\n}\r\ncatch (error) {\r\n    Zabbix.log(3, '[Keep Webhook] Notification failed : ' + error);\r\n    throw 'Keep notification failed : ' + error;\r\n}\r\n".replace(
            "%%KEEP_API_URL%%", keep_api_url
        ).replace(
            "%%API_KEY%%", api_key
        )
        self.logger.info("Getting existing media types")
        existing_media_types = self.__send_request("mediatype.get")
        self.logger.info("Got existing media types")
        media_type_exists = [
            mt for mt in existing_media_types.get("result", []) if mt["name"] == name
        ]
        if media_type_exists:
            existing_media_type = media_type_exists[0]
            self.logger.info("Updating existing media type")
            self.__send_request(
                "mediatype.update",
                {
                    "mediatypeid": str(existing_media_type["mediatypeid"]),
                    "script": script,
                    "status": "0",
                },
            )
            self.logger.info("Updated existing media type")
        else:
            self.logger.info("Creating new media type")
            params = {
                "name": name,
                "type": "4",  # webhook
                "parameters": [
                    {"name": "message", "value": "{ALERT.MESSAGE}"},
                    {"name": "ALERT.SUBJECT", "value": "{ALERT.SUBJECT}"},
                    {"name": "EVENT.ACK.STATUS", "value": "{EVENT.ACK.STATUS}"},
                    {"name": "lastReceived", "value": "{EVENT.DATE}"},
                    {"name": "id", "value": "{EVENT.ID}"},
                    {"name": "name", "value": "{EVENT.NAME}"},
                    {"name": "EVENT.NSEVERITY", "value": "{EVENT.NSEVERITY}"},
                    {"name": "EVENT.OPDATA", "value": "{EVENT.OPDATA}"},
                    {"name": "EVENT.RECOVERY.DATE", "value": "{EVENT.RECOVERY.DATE}"},
                    {"name": "EVENT.RECOVERY.TIME", "value": "{EVENT.RECOVERY.TIME}"},
                    {"name": "EVENT.RECOVERY.VALUE", "value": "{EVENT.RECOVERY.VALUE}"},
                    {"name": "EVENT.SEVERITY", "value": "{EVENT.SEVERITY}"},
                    {"name": "EVENT.TAGS", "value": "{EVENT.TAGS}"},
                    {"name": "EVENT.TIME", "value": "{EVENT.TIME}"},
                    {"name": "EVENT.UPDATE.ACTION", "value": "{EVENT.UPDATE.ACTION}"},
                    {"name": "EVENT.UPDATE.DATE", "value": "{EVENT.UPDATE.DATE}"},
                    {"name": "EVENT.UPDATE.MESSAGE", "value": "{EVENT.UPDATE.MESSAGE}"},
                    {"name": "EVENT.UPDATE.STATUS", "value": "{EVENT.UPDATE.STATUS}"},
                    {"name": "EVENT.UPDATE.TIME", "value": "{EVENT.UPDATE.TIME}"},
                    {"name": "EVENT.VALUE", "value": "{EVENT.VALUE}"},
                    {"name": "service", "value": "{HOST.HOST}"},
                    {"name": "HOST.IP", "value": "{HOST.IP}"},
                    {"name": "HOST.NAME", "value": "{HOST.NAME}"},
                    {"name": "description", "value": "{TRIGGER.DESCRIPTION}"},
                    {"name": "TRIGGER.ID", "value": "{TRIGGER.ID}"},
                    {"name": "TRIGGER.NAME", "value": "{TRIGGER.NAME}"},
                    {"name": "severity", "value": "{TRIGGER.SEVERITY}"},
                    {"name": "status", "value": "{TRIGGER.STATUS}"},
                    {"name": "TRIGGER.URL", "value": "{TRIGGER.URL}"},
                    {"name": "TRIGGER.VALUE", "value": "{TRIGGER.VALUE}"},
                    {"name": "USER.FULLNAME", "value": "{USER.FULLNAME}"},
                ],
                "script": script,
                "process_tags": 1,
                "show_event_menu": 0,
                "description": "Please refer to https://docs.keephq.dev/platform/core/providers/documentation/zabbix-provider or https://platform.keephq.dev/",
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

    def format_alert(event: dict) -> AlertDto:
        environment = "unknown"
        tags = event.get("tags", {})
        if isinstance(tags, dict):
            environment = tags.get("environment", "unknown")
        return AlertDto(
            **event, environment=environment, pushed=True, source=["zabbix"]
        )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

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
        provider_id="zabbix",
        provider_type="zabbix",
        provider_config=provider_config,
    )
    provider.setup_webhook(
        "e1faa321-35df-486b-8fa8-3601ee714011", "http://localhost:8080", "abc"
    )
