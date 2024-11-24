"""
Statuscake is a class that provides a way to read alerts from the Statuscake API and install webhook in StatuCake
"""

import dataclasses
from typing import List
from urllib.parse import urlencode, urljoin

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class StatuscakeProviderAuthConfig:
    """
    StatuscakeProviderAuthConfig is a class that holds the authentication information for the StatuscakeProvider.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Statuscake API Key",
            "sensitive": True,
        },
        default=None,
    )


class StatuscakeProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Statuscake"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="alerts",
            description="Read alerts from Statuscake",
        )
    ]

    SEVERITIES_MAP = {
        "high": AlertSeverity.HIGH,
    }

    STATUS_MAP = {
        "Up": AlertStatus.RESOLVED,
        "Down": AlertStatus.FIRING,
    }

    FINGERPRINT_FIELDS = ["test_id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for StatucCake api requests.
        """
        host = "https://api.statuscake.com/v1/"
        url = urljoin(
            host,
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"
        return url

    def validate_scopes(self):
        """
        Validate that the user has the required scopes to use the provider
        """
        try:
            response = requests.get(
                url=self.__get_url(paths=["uptime"]),
                headers=self.__get_auth_headers(),
            )

            if response.status_code == 200:
                scopes = {"alerts": True}

            else:
                self.logger.error(
                    "Unable to read alerts from Statuscake, statusCode: %s",
                    response.status_code,
                )
                scopes = {
                    "alerts": f"Unable to read alerts from Statuscake, statusCode: {response.status_code}"
                }

        except Exception as e:
            self.logger.error("Error validating scopes for Statuscake: %s", e)
            scopes = {"alerts": f"Error validating scopes for Statuscake: {e}"}

        return scopes

    def validate_config(self):
        self.authentication_config = StatuscakeProviderAuthConfig(
            **self.config.authentication
        )
        if self.authentication_config.api_key is None:
            raise ValueError("Statuscake API Key is required")

    def __get_auth_headers(self):
        if self.authentication_config.api_key is not None:
            return {
                "Authorization": f"Bearer {self.authentication_config.api_key}",
                "Content-Type": "application/x-www-form-urlencoded",
            }

    def __get_paginated_data(self, paths: list, query_params: dict = {}):
        data = []
        try:
            page = 1
            while True:
                self.logger.info(f"Getting page: {page} for {paths}")
                response = requests.get(
                    url=self.__get_url(
                        paths=paths, query_params={**query_params, "page": page}
                    ),
                    headers=self.__get_auth_headers(),
                )

                if not response.ok:
                    raise Exception(response.text)

                response = response.json()
                data.extend(response["data"])
                if page == response["metadata"]["page_count"]:
                    break
            return data

        except Exception as e:
            self.logger.error(
                f"Error while getting {paths}", extra={"exception": str(e)}
            )
            raise e

    def __update_contact_group(self, contact_group_id, keep_api_url):
        try:
            response = requests.put(
                url=self.__get_url(["contact-groups", contact_group_id]),
                headers=self.__get_auth_headers(),
                data={
                    "ping_url": keep_api_url,
                },
            )
            if response.status_code != 204:
                raise Exception(response.text)
        except Exception as e:
            self.logger.error(
                "Error while updating contact group", extra={"exception": str(e)}
            )
            raise e

    def __create_contact_group(self, keep_api_url: str, contact_group_name: str):
        try:
            response = requests.post(
                url=self.__get_url(paths=["contact-groups"]),
                headers=self.__get_auth_headers(),
                data={
                    "ping_url": keep_api_url,
                    "name": contact_group_name,
                },
            )
            if response.status_code != 201:
                raise Exception(response.text)
            self.logger.info("Successfully created contact group")
            return response.json()["data"]["new_id"]
        except Exception as e:
            self.logger.error(
                "Error while creating contact group", extra={"exception": str(e)}
            )
            raise e

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        # Getting all the contact groups
        self.logger.info("Attempting to install webhook in statuscake")
        keep_api_url = f"{keep_api_url}&api_key={api_key}"
        contact_group_name = f"Keep-{self.provider_id}"
        contact_groups = self.__get_paginated_data(paths=["contact-groups"])
        for contact_group in contact_groups:
            if contact_group["name"] == contact_group_name:
                self.logger.info(
                    "Webhook already exists, updating the ping_url, just for safe measures"
                )
                contact_group_id = contact_group["id"]
                self.__update_contact_group(
                    contact_group_id=contact_group_id, keep_api_url=keep_api_url
                )
                break
        else:
            self.logger.info("Creating a new contact group")
            contact_group_id = self.__create_contact_group(
                contact_group_name=contact_group_name, keep_api_url=keep_api_url
            )

        alerts_to_update = ["heartbeat", "uptime", "pagespeed", "ssl"]

        for alert_type in alerts_to_update:
            alerts = self.__get_paginated_data(paths=[alert_type])
            for alert in alerts:
                if contact_group_id not in alert["contact_groups"]:
                    alert["contact_groups"].append(contact_group_id)
                    self.__update_alert(
                        data={"contact_groups[]": alert["contact_groups"]},
                        paths=[alert_type, alert["id"]],
                    )

    def __update_alert(self, data: dict, paths: list):
        try:
            self.logger.info(f"Attempting to updated alert: {paths}")
            response = requests.put(
                url=self.__get_url(paths=paths),
                headers=self.__get_auth_headers(),
                data=data,
            )
            if not response.ok:
                raise Exception(response.text)
            self.logger.info(
                "Successfully updated alert", extra={"data": data, "paths": paths}
            )
        except Exception as e:
            self.logger.error("Error while updating alert", extra={"exception": str(e)})
            raise e

    def __get_heartbeat_alerts_dto(self) -> list[AlertDto]:

        response = self.__get_paginated_data(paths=["heartbeat"])

        return [
            AlertDto(
                id=alert["id"],
                name=alert["name"],
                status=alert["status"],
                url=alert["website_url"],
                uptime=alert["uptime"],
                source="statuscake",
            )
            for alert in response
        ]

    def __get_pagespeed_alerts_dto(self) -> list[AlertDto]:

        response = self.__get_paginated_data(paths=["pagespeed"])

        return [
            AlertDto(
                name=alert["name"],
                url=alert["website_url"],
                location=alert["location"],
                alert_smaller=alert["alert_smaller"],
                alert_bigger=alert["alert_bigger"],
                alert_slower=alert["alert_slower"],
                status=alert["status"],
                source="statuscake",
            )
            for alert in response
        ]

    def __get_ssl_alerts_dto(self) -> list[AlertDto]:

        response = self.__get_paginated_data(paths=["ssl"])

        return [
            AlertDto(
                id=alert["id"],
                url=alert["website_url"],
                issuer_common_name=alert["issuer_common_name"],
                cipher=alert["cipher"],
                cipher_score=alert["cipher_score"],
                certificate_score=alert["certificate_score"],
                certificate_status=alert["certificate_status"],
                valid_from=alert["valid_from"],
                valid_until=alert["valid_until"],
                source="statuscake",
            )
            for alert in response
        ]

    def __get_uptime_alerts_dto(self) -> list[AlertDto]:

        response = self.__get_paginated_data(paths=["uptime"])

        return [
            AlertDto(
                id=alert["id"],
                name=alert["name"],
                status=alert["status"],
                url=alert["website_url"],
                uptime=alert["uptime"],
                source="statuscake",
            )
            for alert in response
        ]

    def _get_alerts(self) -> list[AlertDto]:
        alerts = []
        try:
            self.logger.info("Collecting alerts (heartbeats) from Statuscake")
            heartbeat_alerts = self.__get_heartbeat_alerts_dto()
            alerts.extend(heartbeat_alerts)
        except Exception as e:
            self.logger.error("Error getting heartbeat from Statuscake: %s", e)

        try:
            self.logger.info("Collecting alerts (pagespeed) from Statuscake")
            pagespeed_alerts = self.__get_pagespeed_alerts_dto()
            alerts.extend(pagespeed_alerts)
        except Exception as e:
            self.logger.error("Error getting pagespeed from Statuscake: %s", e)

        try:
            self.logger.info("Collecting alerts (ssl) from Statuscake")
            ssl_alerts = self.__get_ssl_alerts_dto()
            alerts.extend(ssl_alerts)
        except Exception as e:
            self.logger.error("Error getting ssl from Statuscake: %s", e)

        try:
            self.logger.info("Collecting alerts (uptime) from Statuscake")
            uptime_alerts = self.__get_uptime_alerts_dto()
            alerts.extend(uptime_alerts)
        except Exception as e:
            self.logger.error("Error getting uptime from Statuscake: %s", e)

        return alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # https://www.statuscake.com/kb/knowledge-base/how-to-use-the-web-hook-url/
        status = StatuscakeProvider.STATUS_MAP.get(
            event.get("Status"), AlertStatus.FIRING
        )

        # Statuscake does not provide severity information
        severity = AlertSeverity.HIGH

        alert = AlertDto(
            id=event.get("TestID", event.get("Name")),
            name=event.get("Name"),
            status=status if status is not None else AlertStatus.FIRING,
            severity=severity,
            url=event.get("URL", None),
            ip=event.get("IP", None),
            tags=event.get("Tags", None),
            test_id=event.get("TestID", None),
            method=event.get("Method", None),
            checkrate=event.get("Checkrate", None),
            status_code=event.get("StatusCode", None),
            source=["statuscake"],
        )
        alert.fingerprint = (
            StatuscakeProvider.get_alert_fingerprint(
                alert,
                (StatuscakeProvider.FINGERPRINT_FIELDS),
            )
            if event.get("TestID", None)
            else None
        )

        return alert


if __name__ == "__main__":
    pass
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    statuscake_api_key = os.environ.get("STATUSCAKE_API_KEY")

    if statuscake_api_key is None:
        raise Exception("STATUSCAKE_API_KEY is required")

    config = ProviderConfig(
        description="Statuscake Provider",
        authentication={"api_key": statuscake_api_key},
    )

    provider = StatuscakeProvider(
        context_manager,
        provider_id="statuscake",
        config=config,
    )

    provider._get_alerts()
