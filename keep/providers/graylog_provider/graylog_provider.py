"""
Graylog Provider is a class that allows to install webhooks in Graylog.
"""

# Documentation for older versions of graylog: https://github.com/Graylog2/documentation

import dataclasses
import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import List
from urllib.parse import urlencode, urljoin, urlparse

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class ResourceAlreadyExists(Exception):
    def __init__(self, *args):
        super().__init__(*args)


@pydantic.dataclasses.dataclass
class GraylogProviderAuthConfig:
    """
    Graylog authentication configuration.
    """

    graylog_user_name: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Username",
            "hint": "Your Username associated with the Access Token",
        },
    )
    graylog_access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Graylog Access Token",
            "hint": "Graylog Access Token ",
            "sensitive": True,
        },
    )
    deployment_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Deployment Url",
            "hint": "Example: http://127.0.0.1:9000",
        },
    )


class GraylogProvider(BaseProvider):
    """Install Webhooks and receive alerts from Graylog."""

    PROVIDER_CATEGORY = ["Monitoring"]
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
💡 For more details on how to configure Graylog to send alerts to Keep, see the [Keep documentation](https://docs.keephq.dev/providers/documentation/graylog-provider). 💡

To send alerts from Graylog to Keep, Use the following webhook url to configure Graylog send alerts to Keep:

1. In Graylog, from the Topbar, go to `Alerts` > `Notifications`.
2. Click "Create Notification".
3. In the New Notification form, configure:

**Note**: For Graylog v4.x please set the **URL** to `{keep_webhook_api_url}?api_key={api_key}`.

- **Display Name**: keep-graylog-webhook-integration
- **Title**: keep-graylog-webhook-integration
- **Notification Type**: Custom HTTP Notification
- **URL**: {keep_webhook_api_url}  # Whitelist this URL
- **Headers**: X-API-KEY:{api_key}
4. Erase the Body Template.
5. Click on "Create Notification".
6. Go the the `Event Definitions` tab, and select the Event Definition that will trigger the alert you want to send to Keep and click on More > Edit.
7. Go to "Notifications" tab.
8. Click on "Add Notification" and select the "keep-graylog-webhook-integration" that you created in step 3.
9. Click on "Add Notification".
10. Click `Next` > `Update` event definition
"""
    PROVIDER_DISPLAY_NAME = "Graylog"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is Authorized",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Rules Reader",
        ),
        ProviderScope(
            name="authorized",
            description="Required privileges",
            mandatory=True,
            mandatory_for_webhook=True,
            alias="Rules Reader",
        ),
    ]

    FINGERPRINT_FIELDS = ["event_definition_id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._host = None
        self.is_v4 = self.__get_graylog_version().startswith("4")

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Graylog provider.
        """
        self.logger.debug("Validating configuration for Graylog provider")
        self.authentication_config = GraylogProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def graylog_host(self):
        self.logger.debug("Fetching Graylog host")
        if self._host:
            self.logger.debug("Returning cached Graylog host")
            return self._host

        # Handle host determination logic with logging
        if self.authentication_config.deployment_url.startswith(
            "http://"
        ) or self.authentication_config.deployment_url.startswith("https://"):
            self.logger.info("Using supplied Graylog host with protocol")
            self._host = self.authentication_config.deployment_url
            return self._host

        # Otherwise, attempt to use https
        try:
            self.logger.debug(
                f"Trying HTTPS for {self.authentication_config.deployment_url}"
            )
            requests.get(
                f"https://{self.authentication_config.deployment_url}",
                verify=False,
            )
            self.logger.info("HTTPS protocol confirmed")
            self._host = f"https://{self.authentication_config.deployment_url}"
        except requests.exceptions.SSLError:
            self.logger.warning("SSL error encountered, falling back to HTTP")
            self._host = f"http://{self.authentication_config.deployment_url}"
        except Exception as e:
            self.logger.error(
                "Failed to determine Graylog host", extra={"exception": str(e)}
            )
            self._host = self.authentication_config.deployment_url.rstrip("/")

        return self._host

    @property
    def _headers(self):
        return {
            "Accept": "application/json",
            "X-Requested-By": "Keep",
        }

    @property
    def _auth(self):
        return self.authentication_config.graylog_access_token, "token"

    def __get_url(self, paths: List[str] = [], query_params: dict = None, **kwargs):
        """
        Helper method to build the url for Graylog api requests.
        """
        host = self.graylog_host.rstrip("/").rstrip() + "/api/"
        self.logger.info(f"Building URL with host: {host}")
        url = urljoin(
            host,
            "/".join(str(path) for path in paths),
        )

        # add query params
        if query_params:
            url = f"{url}?{urlencode(query_params)}"

        self.logger.debug(f"Constructed URL: {url}")
        return url

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating user scopes for Graylog provider")
        required_role = "Admin"

        try:
            user_response = requests.get(
                url=self.__get_url(
                    paths=["users", self.authentication_config.graylog_user_name]
                ),
                headers=self._headers,
                auth=self._auth,
            )
            self.logger.debug("User information request sent")
            if user_response.status_code != 200:
                raise Exception(user_response.text)

            authenticated = True
            user_response = user_response.json()
            if required_role in user_response["roles"]:
                self.logger.info("User has required admin privileges")
                authorized = True
            else:
                self.logger.warning("User lacks required admin privileges")
                authorized = "Missing admin Privileges"

        except Exception as e:
            self.logger.error(
                "Error while validating user scopes", extra={"exception": str(e)}
            )
            authenticated = str(e)
            authorized = False

        return {
            "authenticated": authenticated,
            "authorized": authorized,
        }

    def __get_graylog_version(self) -> str:
        self.logger.info("Getting graylog version info")
        try:
            version_response = requests.get(url=self.__get_url(), headers=self._headers)
            if version_response.status_code != 200:
                raise Exception(version_response.text)
            version = version_response.json()["version"].strip()
            self.logger.info(f"We are working with Graylog version: {version}")
            return version
        except Exception as e:
            self.logger.error(
                "Error while getting Graylog Version", extra={"exception": str(e)}
            )

    def __get_url_whitelist(self):
        try:
            self.logger.info("Fetching URL Whitelist")
            whitelist_response = requests.get(
                url=self.__get_url(paths=["system/urlwhitelist"]),
                headers=self._headers,
                auth=self._auth,
                timeout=10,
            )
            if whitelist_response.status_code != 200:
                raise Exception(whitelist_response.text)
            self.logger.info("Successfully retrieved URL Whitelist")
            return whitelist_response.json()
        except Exception as e:
            self.logger.error(
                "Error while fetching URL whitelist", extra={"exception": str(e)}
            )
            raise e

    def __update_url_whitelist(self, whitelist):
        try:
            self.logger.info("Updating URL whitelist")
            whitelist_response = requests.put(
                url=self.__get_url(paths=["system/urlwhitelist"]),
                headers=self._headers,
                auth=self._auth,
                json=whitelist,
            )
            if whitelist_response.status_code != 204:
                raise Exception(whitelist_response.text)
            self.logger.info("Successfully updated URL whitelist")
        except Exception as e:
            self.logger.error(
                "Error while updating URL whitelist", extra={"exception": str(e)}
            )
            raise e

    def __get_events(self, page: int, per_page: int):
        self.logger.info(
            f"Fetching events from Graylog (page: {page}, per_page: {per_page})"
        )
        try:
            events_response = requests.get(
                url=self.__get_url(paths=["events", "definitions"]),
                headers=self._headers,
                auth=self._auth,
                params={"page": page, "per_page": per_page},
            )

            if events_response.status_code != 200:
                raise Exception(events_response.text)

            events_response = events_response.json()
            self.logger.info("Successfully fetched events from Graylog")
            return events_response

        except Exception as e:
            self.logger.error(
                "Error while fetching events", extra={"exception": str(e)}
            )
            raise e

    def __update_event(self, event):
        try:
            self.logger.info(f"Updating event with ID: {event['id']}")
            event_update_response = requests.put(
                url=self.__get_url(paths=["events", "definitions", event["id"]]),
                timeout=10,
                json=event,
                auth=self._auth,
                headers=self._headers,
            )

            if event_update_response.status_code != 200:
                raise Exception(event_update_response.text)

            self.logger.info(f"Successfully updated event with ID: {event['id']}")

        except Exception as e:
            self.logger.error(
                f"Error while updating event with ID: {event['id']}",
                extra={"exception": str(e)},
            )
            raise e

    def __get_notification(self, page: int, per_page: int, notification_name: str):
        try:
            self.logger.info(f"Fetching notification: {notification_name}")
            notifications_response = requests.get(
                url=self.__get_url(paths=["events", "notifications"]),
                params={
                    "page": page,
                    "per_page": per_page,
                    "query": f"title:{notification_name}",
                },
                auth=self._auth,
                headers=self._headers,
                timeout=10,
            )
            if notifications_response.status_code != 200:
                raise Exception(notifications_response.text)
            self.logger.info(f"Successfully fetched notification: {notification_name}")
            return notifications_response.json()
        except Exception as e:
            self.logger.error(
                f"Error while fetching notification {notification_name}",
                extra={"exception": str(e)},
            )
            raise e

    def __delete_notification(self, notification_id: str):
        try:
            self.logger.info(
                f"Attempting to delete notification with ID: {notification_id}"
            )
            notification_delete_response = requests.delete(
                url=self.__get_url(paths=["events", "notifications", notification_id]),
                auth=self._auth,
                headers=self._headers,
            )
            if notification_delete_response.status_code != 204:
                raise Exception(notification_delete_response.text)

            self.logger.info(
                f"Successfully deleted notification with ID: {notification_id}"
            )

        except Exception as e:
            self.logger.error(
                f"Error while deleting notification with ID {notification_id}",
                extra={"exception": str(e)},
            )
            raise e

    def __create_notification(self, notification_name: str, notification_body):
        try:
            self.logger.info(f"Attempting to create notification: {notification_name}")
            notification_creation_response = requests.post(
                url=self.__get_url(paths=["events", "notifications"]),
                headers=self._headers,
                auth=self._auth,
                timeout=10,
                json=notification_body,
            )
            if notification_creation_response.status_code != 200:
                raise Exception(notification_creation_response.text)

            self.logger.info(f"Successfully created notification: {notification_name}")
            return notification_creation_response.json()
        except Exception as e:
            self.logger.error(
                f"Error while creating notification {notification_name}",
                extra={"exception": str(e)},
            )
            raise e

    def __update_notification(self, notification_id: str, notification_body):
        try:
            self.logger.info(
                f"Attempting to update notification with ID: {notification_id}"
            )
            notification_update_response = requests.put(
                url=self.__get_url(paths=["events", "notifications", notification_id]),
                headers=self._headers,
                auth=self._auth,
                timeout=10,
                json=notification_body,
            )
            if notification_update_response.status_code != 200:
                raise Exception(notification_update_response.text)

            self.logger.info(
                f"Successfully updated notification with ID: {notification_id}"
            )
            return notification_update_response.json()
        except Exception as e:
            self.logger.error(
                f"Error while updating notification with ID {notification_id}",
                extra={"exception": str(e)},
            )
            raise e

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        self.logger.info("Setting up webhook in Graylog")

        # Extracting provider_id from the keep_api_url
        parsed_url = urlparse(keep_api_url)
        query_params = parsed_url.query
        provider_id = query_params.split("provider_id=")[-1]
        notification_name = f"Keep-{provider_id}"

        if self.is_v4:
            keep_api_url = f"{keep_api_url}&api_key={api_key}"

        try:
            event_definitions = []
            events_1 = self.__get_events(page=1, per_page=100)
            event_definitions.extend(events_1["event_definitions"])
            total_pages = math.ceil(int(events_1["total"]) / 100)

            for page in range(2, total_pages):
                self.logger.debug(f"Fetching events page: {page}")
                event_definitions.extend(
                    self.__get_events(page=page, per_page=100)["event_definitions"]
                )

            # Whitelist URL
            url_whitelist = self.__get_url_whitelist()
            url_found = False
            for entry in url_whitelist["entries"]:
                if entry["value"] == keep_api_url:
                    self.logger.info("URL already whitelisted")
                    url_found = True
                    break
            if not url_found:
                self.logger.info("Adding URL to whitelist")
                url_whitelist["entries"].append(
                    {
                        "id": str(uuid.uuid4()),
                        "title": notification_name,
                        "value": keep_api_url,
                        "type": "literal",
                    }
                )
                self.__update_url_whitelist(url_whitelist)

            # Create notification
            notification = self.__get_notification(
                page=1, per_page=1, notification_name=notification_name
            )

            existing_notification_id = None

            if int(notification["count"]) > 0:
                self.logger.info("Notification already exists, deleting it")

                # We need to clean up the previously installed notification
                existing_notification_id = notification["notifications"][0]["id"]

                self.__delete_notification(notification_id=existing_notification_id)

            self.logger.info("Creating new notification")
            if self.is_v4:
                config = {"type": "http-notification-v1", "url": keep_api_url}
            else:
                config = {
                    "type": "http-notification-v2",
                    "basic_auth": None,
                    "api_key_as_header": False,
                    "api_key": "",
                    "api_secret": None,
                    "url": keep_api_url,
                    "skip_tls_verification": True,
                    "method": "POST",
                    "time_zone": "UTC",
                    "content_type": "JSON",
                    "headers": f"X-API-KEY:{api_key}",
                    "body_template": "",
                }
            notification_body = {
                "title": notification_name,
                "description": "Hello, this Notification is created by Keep, please do not change the title.",
                "config": config,
            }
            new_notification = self.__create_notification(
                notification_name=notification_name, notification_body=notification_body
            )

            for event_definition in event_definitions:
                if (
                    not self.is_v4
                    and event_definition["_scope"] == "SYSTEM_NOTIFICATION_EVENT"
                ):
                    self.logger.info("Skipping SYSTEM_NOTIFICATION_EVENT")
                    continue
                self.logger.info(f"Updating event with ID: {event_definition['id']}")

                # Attempting to clean up the deleted notification from the event, it is not handled well in Graylog v4.
                for ind, notification in enumerate(event_definition["notifications"]):
                    if notification["notification_id"] == existing_notification_id:
                        event_definition["notifications"].pop(ind)
                        break

                event_definition["notifications"].append(
                    {"notification_id": new_notification["id"]}
                )
                self.__update_event(event=event_definition)

            self.logger.info("Webhook setup completed successfully")
        except Exception as e:
            self.logger.error(
                "Error while setting up webhook", extra={"exception": str(e)}
            )
            raise e

    @staticmethod
    def __map_event_to_alert(event: dict) -> AlertDto:
        alert = AlertDto(
            id=event["event"]["id"],
            name=event.get("event_definition_title", event["event"]["message"]),
            severity=[AlertSeverity.LOW, AlertSeverity.WARNING, AlertSeverity.HIGH][
                int(event["event"]["priority"]) - 1
            ],
            description=event.get("event_definition_description", None),
            event_definition_id=event["event"]["event_definition_id"],
            origin_context=event["event"].get("origin_context", None),
            status=AlertStatus.FIRING,
            lastReceived=datetime.fromisoformat(
                event["event"]["timestamp"].replace("z", "")
            )
            .replace(tzinfo=timezone.utc)
            .isoformat(),
            message=event["event"].get("message", None),
            source=["graylog"],
        )

        alert.fingerprint = GraylogProvider.get_alert_fingerprint(
            alert, GraylogProvider.FINGERPRINT_FIELDS
        )

        return alert

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: BaseProvider | None = None
    ) -> AlertDto:
        return GraylogProvider.__map_event_to_alert(event=event)

    @classmethod
    def simulate_alert(cls) -> dict:
        import random
        import string

        from keep.providers.graylog_provider.alerts_mock import ALERTS

        # Use the provided ALERTS structure
        alert_data = ALERTS.copy()

        # Start with the base event payload
        simulated_alert = alert_data["event"]

        alert_data["event_definition_title"] = random.choice(
            [
                "EventDefinition - 1",
                "EventDefinition - 2",
                "EventDefinition - 3",
            ]
        )

        alert_data["event_definition_description"] = random.choice(
            [
                "Description - add",
                "Description - commit",
                "Description - push",
            ]
        )

        # Apply variability to the event message and priority
        simulated_alert["message"] = alert_data["event_definition_title"]
        simulated_alert["priority"] = random.choice([1, 2, 3])
        chars = string.ascii_uppercase + string.digits
        # Generate a random ID of specified length
        random_id = "".join(random.choice(chars) for _ in range(25))
        simulated_alert["id"] = random_id

        simulated_alert["event_definition_id"] = alert_data["event_definition_id"] = (
            "".join(
                random.choice(string.ascii_lowercase + string.digits) for _ in range(24)
            )
        )

        # Set the current timestamp
        simulated_alert["timestamp"] = datetime.now().isoformat()

        # Apply variability to replay_info
        replay_info = simulated_alert.get("replay_info", {})
        replay_info["timerange_start"] = (
            datetime.now() - timedelta(hours=1)
        ).isoformat()
        replay_info["timerange_end"] = datetime.now().isoformat()

        simulated_alert["replay_info"] = replay_info

        return alert_data

    def __get_alerts(self, json_data: dict):
        try:
            self.logger.info(
                f"Fetching alerts (page: {json_data['page']}, per_page: {json_data['per_page']})"
            )
            alert_response = requests.post(
                url=self.__get_url(paths=["events", "search"]),
                headers=self._headers,
                auth=self._auth,
                timeout=10,
                json=json_data,
            )

            if alert_response.status_code != 200:
                raise Exception(alert_response.text)

            self.logger.info("Successfully fetched alerts")
            return alert_response.json()

        except Exception as e:
            self.logger.error(
                "Error while fetching alerts", extra={"exception": str(e)}
            )
            raise e

    def _get_alerts(self) -> list[AlertDto]:
        self.logger.info("Getting alerts from Graylog")
        json_data = {
            "query": "",
            "page": 1,
            "per_page": 1000,
            "filter": {
                "alerts": "only",
            },
            "timerange": {
                "range": 1 * 24 * 60 * 60,
                "type": "relative",
            },
        }
        all_alerts = []
        alerts_1 = self.__get_alerts(json_data=json_data)
        all_alerts.extend(alerts_1["events"])
        total_events = max(10, math.ceil(alerts_1["total_events"] / 1000))

        for page in range(2, total_events + 1):
            self.logger.debug(f"Fetching alerts page: {page}")
            json_data["page"] = page
            alerts = self.__get_alerts(json_data=json_data)
            all_alerts.extend(alerts["events"])

        self.logger.info("Successfully fetched all alerts")
        return [
            GraylogProvider.__map_event_to_alert(event=event) for event in all_alerts
        ]

    def _query(self, events_search_parameters: dict, **kwargs: dict):
        self.logger.info("Querying Graylog with specified parameters")
        alerts = self.__get_alerts(json_data=events_search_parameters)["events"]
        return [GraylogProvider.__map_event_to_alert(event=event) for event in alerts]
