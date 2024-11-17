import dataclasses
import datetime
import hashlib
import json
import os
import time
import typing
import uuid

import pydantic
import requests

from keep.api.models.alert import (
    AlertDto,
    AlertSeverity,
    AlertStatus,
    IncidentDto,
    IncidentSeverity,
    IncidentStatus,
)
from keep.api.models.db.topology import TopologyServiceInDto
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import (
    BaseIncidentProvider,
    BaseProvider,
    BaseTopologyProvider,
)
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

# Todo: think about splitting in to PagerdutyIncidentsProvider and PagerdutyAlertsProvider
# Read this: https://community.pagerduty.com/forum/t/create-incident-using-python/3596/3


@pydantic.dataclasses.dataclass
class PagerdutyProviderAuthConfig:
    routing_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Routing Key (an integration or ruleset key)",
        },
        default=None,
    )
    api_key: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Api Key (a user or team API key)",
            "sensitive": True,
        },
        default=None,
    )
    oauth_data: dict = dataclasses.field(
        metadata={
            "description": "For oauth flow",
            "required": False,
            "sensitive": True,
            "hidden": True,
        },
        default="",
    )

    service_id: str | None = dataclasses.field(
        metadata={
            "required": False,
            "description": "Service Id (if provided, keep will only operate on this service)",
            "sensitive": False,
        },
        default=None,
    )
    oauth_data: dict = dataclasses.field(
        metadata={
            "description": "For oauth flow",
            "required": False,
            "sensitive": True,
            "hidden": True,
        },
        default="",
    )


class PagerdutyProvider(BaseTopologyProvider, BaseIncidentProvider):
    """Pull alerts and query incidents from PagerDuty."""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents_read",
            description="Read incidents data.",
            mandatory=True,
            alias="Incidents Data Read",
        ),
        ProviderScope(
            name="incidents_write",
            description="Write incidents.",
            mandatory=False,
            alias="Incidents Write",
        ),
        ProviderScope(
            name="webhook_subscriptions_read",
            description="Read webhook data.",
            mandatory=False,
            mandatory_for_webhook=True,
            alias="Webhooks Data Read",
        ),
        ProviderScope(
            name="webhook_subscriptions_write",
            description="Write webhooks.",
            mandatory=False,
            mandatory_for_webhook=True,
            alias="Webhooks Write",
        ),
    ]
    BASE_API_URL = "https://api.pagerduty.com"
    SUBSCRIPTION_API_URL = f"{BASE_API_URL}/webhook_subscriptions"
    PROVIDER_DISPLAY_NAME = "PagerDuty"
    ALERT_SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }
    INCIDENT_SEVERITIES_MAP = {
        "P1": IncidentSeverity.CRITICAL,
        "P2": IncidentSeverity.HIGH,
        "P3": IncidentSeverity.WARNING,
        "P4": IncidentSeverity.INFO,
    }
    ALERT_STATUS_MAP = {
        "triggered": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
    }
    ALERT_STATUS_TO_EVENT_TYPE_MAP = {
        AlertStatus.FIRING.value: "trigger",
        AlertStatus.RESOLVED.value: "resolve",
        AlertStatus.ACKNOWLEDGED.value: "acknowledge",
    }
    INCIDENT_STATUS_MAP = {
        "triggered": IncidentStatus.FIRING,
        "acknowledged": IncidentStatus.ACKNOWLEDGED,
        "resolved": IncidentStatus.RESOLVED,
    }

    BASE_OAUTH_URL = "https://identity.pagerduty.com"
    PAGERDUTY_CLIENT_ID = os.environ.get("PAGERDUTY_CLIENT_ID")
    PAGERDUTY_CLIENT_SECRET = os.environ.get("PAGERDUTY_CLIENT_SECRET")
    OAUTH2_URL = (
        f"{BASE_OAUTH_URL}/oauth/authorize?client_id={PAGERDUTY_CLIENT_ID}&response_type=code"
        if PAGERDUTY_CLIENT_ID is not None and PAGERDUTY_CLIENT_SECRET is not None
        else None
    )

    FINGERPRINT_FIELDS = ["alert_key"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

        if self.authentication_config.oauth_data:
            last_fetched_at = self.authentication_config.oauth_data["last_fetched_at"]
            expires_in: float | None = self.authentication_config.oauth_data.get(
                "expires_in", None
            )
            if expires_in:
                # Calculate expiration time by adding expires_in to last_fetched_at
                expiration_time = last_fetched_at + expires_in - 600

                # Check if the current epoch time (in seconds) has passed the expiration time
                if time.time() <= expiration_time:
                    self.logger.debug("access_token is still valid")
                    return

            self.logger.info("Refreshing access token")
            self.__refresh_token()
        elif (
            self.authentication_config.api_key or self.authentication_config.routing_key
        ):
            # No need to do anything
            return
        else:
            raise Exception("WTF Exception: No authentication provided")

    def __refresh_token(self):
        """
        Refresh the access token using the refresh token.
        """
        # Using the refresh token to get the access token
        try:
            access_token_response = requests.post(
                url=f"{PagerdutyProvider.BASE_OAUTH_URL}/oauth/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "grant_type": "refresh_token",
                    "client_id": PagerdutyProvider.PAGERDUTY_CLIENT_ID,
                    "client_secret": PagerdutyProvider.PAGERDUTY_CLIENT_SECRET,
                    "refresh_token": f'{self.authentication_config.oauth_data["refresh_token"]}',
                },
            )
            access_token_response.raise_for_status()
            access_token_response = access_token_response.json()
            self.config.authentication["oauth_data"] = {
                "access_token": access_token_response["access_token"],
                "refresh_token": access_token_response["refresh_token"],
                "expires_in": access_token_response["expires_in"],
                "last_fetched_at": time.time(),
            }
        except Exception:
            self.logger.exception(
                "Error while refreshing token",
            )
            raise

    def validate_config(self):
        self.authentication_config = PagerdutyProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.routing_key
            and not self.authentication_config.api_key
            and not self.authentication_config.oauth_data
        ):
            raise ProviderConfigException(
                "PagerdutyProvider requires either routing_key or api_key or OAuth configuration",
                provider_id=self.provider_id,
            )

    @staticmethod
    def oauth2_logic(**payload) -> dict:
        """
        OAuth2 callback logic for Pagerduty.

        Raises:
            Exception: No code verifier
            Exception: No code
            Exception: No redirect URI
            Exception: Failed to get access token
            Exception: No access token

        Returns:
            dict: access token and refresh token
        """
        code_verifier = payload.get("verifier")
        if not code_verifier:
            raise Exception("No code verifier")

        code = payload.get("code")
        if not code:
            raise Exception("No code")

        redirect_uri = payload.get("redirect_uri")
        if not redirect_uri:
            raise Exception("Missing redirect URI")

        access_token_params = {
            "client_id": PagerdutyProvider.PAGERDUTY_CLIENT_ID,
            "client_secret": PagerdutyProvider.PAGERDUTY_CLIENT_SECRET,
            "code_verifier": code_verifier,
            "code": code,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        try:
            access_token_response = requests.post(
                url=f"{PagerdutyProvider.BASE_OAUTH_URL}/oauth/token",
                data=access_token_params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            access_token_response.raise_for_status()
            access_token_response = access_token_response.json()
        except Exception as e:
            raise Exception(e)

        access_token = access_token_response.get("access_token")
        if not access_token:
            raise Exception("No access token provided")
        return {
            "oauth_data": {
                "access_token": access_token_response["access_token"],
                "refresh_token": access_token_response["refresh_token"],
                "last_fetched_at": time.time(),
                "expires_in": access_token_response.get("expires_in", None),
            }
        }

    def __get_headers(self, **kwargs):
        if self.authentication_config.api_key or self.authentication_config.routing_key:
            return {
                "Accept": "application/vnd.pagerduty+json;version=2",
                "Content-Type": "application/json",
                "Authorization": f"Token token={self.authentication_config.api_key}",
                **kwargs,
            }
        elif self.authentication_config.oauth_data:
            return {
                "Accept": "application/vnd.pagerduty+json;version=2",
                "Authorization": f"Bearer {self.authentication_config.oauth_data['access_token']}",
                "Content-Type": "application/json",
            }

    def validate_scopes(self):
        """
        Validate that the provider has the required scopes.
        """
        headers = self.__get_headers()
        scopes = {}
        for scope in self.PROVIDER_SCOPES:

            # If the provider is installed using a routing key, we skip scopes validation for now.
            if self.authentication_config.routing_key:
                if scope.name == "incidents_read":
                    # This is because incidents_read is mandatory and will not let the provider install otherwise
                    scopes[scope.name] = True
                else:
                    scopes[scope.name] = "Skipped due to routing key"
                continue

            try:
                # Todo: how to check validity for write scopes?
                if scope.name.startswith("incidents"):
                    response = requests.get(
                        f"{self.BASE_API_URL}/incidents",
                        headers=headers,
                    )
                elif scope.name.startswith("webhook_subscriptions"):
                    response = requests.get(
                        self.SUBSCRIPTION_API_URL,
                        headers=headers,
                    )
                if response.ok:
                    scopes[scope.name] = True
                else:
                    try:
                        response_json = response.json()
                        scopes[scope.name] = str(
                            response_json.get("error", response.reason)
                        )
                    except Exception:
                        scopes[scope.name] = response.reason
            except Exception as e:
                self.logger.exception("Error validating scopes")
                scopes[scope.name] = str(e)
        return scopes

    def _build_alert(
        self,
        title: str,
        alert_body: str,
        dedup: str | None = None,
        severity: typing.Literal["critical", "error", "warning", "info"] | None = None,
        event_type: typing.Literal["trigger", "acknowledge", "resolve"] | None = None,
        source: str = "custom_event",
    ) -> typing.Dict[str, typing.Any]:
        """
        Builds the payload for an event alert.

        Args:
            title: Title of alert
            alert_body: UTF-8 string of custom message for alert. Shown in incident body
            dedup: Any string, max 255, characters used to deduplicate alerts
            event_type: The type of event to send to PagerDuty

        Returns:
            Dictionary of alert body for JSON serialization
        """
        if not severity:
            # this is the default severity
            severity = "critical"
            # try to get it automatically from the context (if there's an alert, for example)
            if self.context_manager.event_context:
                severity = self.context_manager.event_context.severity

        if not event_type:
            event_type = "trigger"
            # try to get it automatically from the context (if there's an alert, for example)
            if self.context_manager.event_context:
                status = self.context_manager.event_context.status
                event_type = PagerdutyProvider.ALERT_STATUS_TO_EVENT_TYPE_MAP.get(
                    status, "trigger"
                )

        if not dedup:
            # If no dedup is given, use epoch timestamp
            dedup = str(datetime.datetime.now().timestamp())
            # Try to get it from the context (if there's an alert, for example)
            if self.context_manager.event_context:
                dedup = self.context_manager.event_context.fingerprint

        return {
            "routing_key": self.authentication_config.routing_key,
            "event_action": event_type,
            "dedup_key": dedup,
            "payload": {
                "summary": title,
                "source": source,
                "severity": severity,
                "custom_details": {
                    "alert_body": alert_body,
                },
            },
        }

    def _send_alert(
        self,
        title: str,
        body: str,
        dedup: str | None = None,
        severity: typing.Literal["critical", "error", "warning", "info"] | None = None,
        event_type: typing.Literal["trigger", "acknowledge", "resolve"] | None = None,
        source: str = "custom_event",
    ):
        """
        Sends PagerDuty Alert

        Args:
            title: Title of the alert.
            alert_body: UTF-8 string of custom message for alert. Shown in incident body
            dedup: Any string, max 255, characters used to deduplicate alerts
            event_type: The type of event to send to PagerDuty
        """
        url = "https://events.pagerduty.com/v2/enqueue"

        payload = self._build_alert(title, body, dedup, severity, event_type, source)
        result = requests.post(url, json=payload)
        result.raise_for_status()

        self.logger.info(
            "Sent alert to PagerDuty",
            extra={
                "status_code": result.status_code,
                "response_text": result.text,
                "routing_key": self.authentication_config.routing_key,
            },
        )
        return result.json()

    def _trigger_incident(
        self,
        service_id: str,
        title: str,
        body: dict,
        requester: str,
        incident_key: str | None = None,
    ):
        """Triggers an incident via the V2 REST API using sample data."""

        if not incident_key:
            incident_key = str(uuid.uuid4()).replace("-", "")

        url = f"{self.BASE_API_URL}/incidents"
        headers = self.__get_headers(From=requester)

        payload = {
            "incident": {
                "type": "incident",
                "title": title,
                "service": {"id": service_id, "type": "service_reference"},
                "incident_key": incident_key,
                "body": body,
            }
        }

        r = requests.post(url, headers=headers, data=json.dumps(payload))
        r.raise_for_status()
        response = r.json()
        self.logger.info("Incident triggered")
        return response

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def setup_incident_webhook(
        self,
        tenant_id: str,
        keep_api_url: str,
        api_key: str,
        setup_alerts: bool = True,
    ):
        self.logger.info("Setting up Pagerduty webhook")

        if self.authentication_config.routing_key:
            self.logger.info("Skipping webhook setup due to routing key")
            return

        headers = self.__get_headers()
        request = requests.get(self.SUBSCRIPTION_API_URL, headers=headers)
        if not request.ok:
            raise Exception("Could not get existing webhooks")
        existing_webhooks = request.json().get("webhook_subscriptions", [])
        webhook_exists = next(
            iter(
                [
                    webhook
                    for webhook in existing_webhooks
                    if keep_api_url == webhook.get("delivery_method", {}).get("url", "")
                ]
            ),
            False,
        )
        webhook_payload = {
            "webhook_subscription": {
                "type": "webhook_subscription",
                "delivery_method": {
                    "type": "http_delivery_method",
                    "url": keep_api_url,
                    "custom_headers": [{"name": "X-API-KEY", "value": api_key}],
                },
                "description": f"Keep Pagerduty webhook ({self.provider_id}) - do not change",
                "events": [
                    "incident.acknowledged",
                    "incident.annotated",
                    "incident.delegated",
                    "incident.escalated",
                    "incident.priority_updated",
                    "incident.reassigned",
                    "incident.reopened",
                    "incident.resolved",
                    "incident.responder.added",
                    "incident.responder.replied",
                    "incident.triggered",
                    "incident.unacknowledged",
                ],
                "filter": (
                    {
                        "type": "service_reference",
                        "id": self.authentication_config.service_id,
                    }
                    if self.authentication_config.service_id
                    else {"type": "account_reference"}
                ),
            },
        }
        if webhook_exists:
            self.logger.info("Webhook already exists, removing and re-creating")
            webhook_id = webhook_exists.get("id")
            request = requests.delete(
                f"{self.SUBSCRIPTION_API_URL}/{webhook_id}", headers=headers
            )
            if not request.ok:
                raise Exception("Could not remove existing webhook")
            self.logger.info("Webhook removed", extra={"webhook_id": webhook_id})

        self.logger.info("Creating Pagerduty webhook")
        request = requests.post(
            self.SUBSCRIPTION_API_URL,
            headers=headers,
            json=webhook_payload,
        )
        if not request.ok:
            self.logger.error("Failed to add webhook", extra=request.json())
            raise Exception("Could not create webhook")
        self.logger.info("Webhook created")

    def _notify(
        self,
        title: str = "",
        alert_body: str = "",
        dedup: str = "",
        service_id: str = "",
        requester: str = "",
        incident_id: str = "",
        event_type: typing.Literal["trigger", "acknowledge", "resolve"] | None = None,
        severity: typing.Literal["critical", "error", "warning", "info"] | None = None,
        source: str = "custom_event",
        **kwargs: dict,
    ):
        """
        Create a PagerDuty alert.
            Alert/Incident is created either via the Events API or the Incidents API.
            See https://community.pagerduty.com/forum/t/create-incident-using-python/3596/3 for more information

        Args:
            kwargs (dict): The providers with context
        """
        if self.authentication_config.routing_key:
            return self._send_alert(
                title,
                alert_body,
                dedup=dedup,
                event_type=event_type,
                source=source,
                severity=severity,
            )
        else:
            return self._trigger_incident(
                service_id, title, alert_body, requester, incident_id
            )
            incident_alerts = [self._format_alert(alert) for alert in incident_alerts]
            incident_dto._alerts = incident_alerts
            incidents.append(incident_dto)
        return incidents

    @staticmethod
    def _get_incident_id(incident_id: str) -> str:
        """
        Create a UUID from the incident id.

        Args:
            incident_id (str): The original incident id

        Returns:
            str: The UUID
        """
        md5 = hashlib.md5()
        md5.update(incident_id.encode("utf-8"))
        return uuid.UUID(md5.hexdigest())

    @staticmethod
    def _format_incident(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> IncidentDto | list[IncidentDto]:

        event = event["event"]["data"]

        # This will be the same for the same incident
        original_incident_id = event.get("id", "ping")

        incident_id = PagerdutyProvider._get_incident_id(original_incident_id)

        status = PagerdutyProvider.INCIDENT_STATUS_MAP.get(
            event.get("status", "firing"), IncidentStatus.FIRING
        )
        priority_summary = (event.get("priority", {}) or {}).get("summary", "P4")
        severity = PagerdutyProvider.INCIDENT_SEVERITIES_MAP.get(
            priority_summary, IncidentSeverity.INFO
        )
        service = event.pop("service", {}).get("summary", "unknown")

        created_at = event.get("created_at")
        if created_at:
            created_at = datetime.datetime.fromisoformat(created_at)
        else:
            created_at = datetime.datetime.now(tz=datetime.timezone.utc)

        return IncidentDto(
            id=incident_id,
            creation_time=created_at,
            user_generated_name=f'PD-{event.get("title", "unknown")}-{original_incident_id}',
            status=status,
            severity=severity,
            alert_sources=["pagerduty"],
            alerts_count=event.get("alert_counts", {}).get("all", 0),
            services=[service],
            is_predicted=False,
            is_confirmed=True,
            # This is the reference to the incident in PagerDuty
            fingerprint=original_incident_id,
        )

    def _query(self, incident_id: str = None):
        incidents = self.__get_all_incidents_or_alerts()
        return (
            next(
                [incident for incident in incidents if incident.id == incident_id],
                None,
            )
            if incident_id
            else incidents
        )

    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # If somebody connected the provider before we refactored it
        old_format_event = event.get("event", {})
        if old_format_event is not None and isinstance(old_format_event, dict):
            return PagerdutyProvider._format_alert_old(event)

        status = PagerdutyProvider.ALERT_STATUS_MAP.get(event.get("status", "firing"))
        severity = PagerdutyProvider.ALERT_SEVERITIES_MAP.get(
            event.get("severity", "info")
        )
        source = ["pagerduty"]
        origin = event.get("body", {}).get("cef_details", {}).get("source_origin")
        fingerprint = event.get("alert_key", event.get("id"))
        if origin:
            source.append(origin)
        return AlertDto(
            id=event.get("id"),
            name=event.get("summary"),
            url=event.get("html_url"),
            service=event.get("service", {}).get("name"),
            lastReceived=event.get("created_at"),
            status=status,
            severity=severity,
            source=source,
            original_alert=event,
            fingerprint=fingerprint,
        )

    def _format_alert_old(event: dict) -> AlertDto:
        actual_event = event.get("event", {})
        data = actual_event.get("data", {})

        event_type = data.get("type", "incident")
        if event_type != "incident":
            return None

        url = data.pop("self", data.pop("html_url", None))
        # format status and severity to Keep format
        status = PagerdutyProvider.ALERT_STATUS_MAP.get(data.pop("status", "firing"))
        priority_summary = (data.get("priority", {}) or {}).get("summary")
        priority = PagerdutyProvider.ALERT_SEVERITIES_MAP.get(priority_summary, "P4")
        last_received = data.pop(
            "created_at", datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        )
        name = data.pop("title")
        service = data.pop("service", {}).get("summary", "unknown")
        environment = next(
            iter(
                [
                    x
                    for x in data.pop("custom_fields", [])
                    if x.get("name") == "environment"
                ]
            ),
            {},
        ).get("value", "unknown")

        last_status_change_by = data.get("last_status_change_by", {}).get("summary")
        acknowledgers = [x.get("summary") for x in data.get("acknowledgers", [])]
        conference_bridge = data.get("conference_bridge", {})
        if isinstance(conference_bridge, dict):
            conference_bridge = conference_bridge.get("summary")
        urgency = data.get("urgency")

        # Additional metadata
        metadata = {
            "urgency": urgency,
            "acknowledgers": acknowledgers,
            "last_updated_by": last_status_change_by,
            "conference_bridge": conference_bridge,
            "impacted_services": service,
        }

        return AlertDto(
            **data,
            url=url,
            status=status,
            lastReceived=last_received,
            name=name,
            severity=priority,
            environment=environment,
            source=["pagerduty"],
            service=service,
            labels=metadata,
        )

    def __get_all_incidents_or_alerts(self, incident_id: str = None):
        self.logger.info(
            "Getting incidents or alerts", extra={"incident_id": incident_id}
        )
        paginated_response = []
        offset = 0
        while True:
            try:
                url = f"{self.BASE_API_URL}/incidents"
                include = []
                resource = "incidents"
                if incident_id is not None:
                    url += f"/{incident_id}/alerts"
                    include = ["teams", "services"]
                    resource = "alerts"
                params = {
                    "include[]": include,
                    "offset": offset,
                    "limit": 100,
                }
                if not incident_id and self.authentication_config.service_id:
                    params["service_ids[]"] = [self.authentication_config.service_id]
                response = requests.get(
                    url=url,
                    headers=self.__get_headers(),
                    params=params,
                )
                response.raise_for_status()
                response = response.json()
            except Exception:
                self.logger.exception("Failed to get incidents or alerts")
                raise
            offset = response.get("offset", 0)
            paginated_response.extend(response.get(resource, []))
            self.logger.info("Fetched incidents or alerts", extra={"offset": offset})
            # No more results
            if not response.get("more", False):
                self.logger.info("No more incidents or alerts")
                break
        self.logger.info(
            "Fetched all incidents or alerts", extra={"count": len(paginated_response)}
        )
        return paginated_response

    def __get_all_services(self, business_services: bool = False):
        all_services = []
        offset = 0
        more = True
        endpoint = "business_services" if business_services else "services"
        while more:
            try:
                services_response = requests.get(
                    url=f"{self.BASE_API_URL}/{endpoint}",
                    headers=self.__get_headers(),
                    params={"include[]": ["teams"], "offset": offset, "limit": 100},
                )
                services_response.raise_for_status()
                services_response = services_response.json()
            except Exception as e:
                self.logger.error("Failed to get all services", extra={"exception": e})
                raise e
            more = services_response.get("more", False)
            offset = services_response.get("offset", 0)
            all_services.extend(services_response.get(endpoint, []))
        return all_services

    def pull_topology(self) -> list[TopologyServiceInDto]:
        # Skipping topology pulling when we're installed with routing_key
        if self.authentication_config.routing_key:
            return []

        all_services = self.__get_all_services()
        all_business_services = self.__get_all_services(business_services=True)
        service_metadata = {}
        for service in all_services:
            service_metadata[service["id"]] = service

        for business_service in all_business_services:
            service_metadata[business_service["id"]] = business_service

        try:
            service_map_response = requests.get(
                url=f"{self.BASE_API_URL}/service_dependencies",
                headers=self.__get_headers(),
            )
            service_map_response.raise_for_status()
            service_map_response = service_map_response.json()
        except Exception:
            self.logger.exception("Error while getting service dependencies")
            raise

        service_topology = {}

        for relationship in service_map_response.get("relationships", []):
            # Extract dependent and supporting service details
            dependent = relationship["dependent_service"]
            supporting = relationship["supporting_service"]

            if dependent["id"] not in service_topology:
                service_topology[dependent["id"]] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=dependent["id"],
                    display_name=service_metadata[dependent["id"]]["name"],
                    description=service_metadata[dependent["id"]]["description"],
                    team=", ".join(
                        team["name"]
                        for team in service_metadata[dependent["id"]].get("teams", [])
                    ),
                )
            if supporting["id"] not in service_topology:
                service_topology[supporting["id"]] = TopologyServiceInDto(
                    source_provider_id=self.provider_id,
                    service=supporting["id"],
                    display_name=service_metadata[supporting["id"]]["name"],
                    description=service_metadata[supporting["id"]]["description"],
                    team=", ".join(
                        team["name"]
                        for team in service_metadata[supporting["id"]].get("teams", [])
                    ),
                )
            service_topology[dependent["id"]].dependencies[supporting["id"]] = "unknown"
        return list(service_topology.values())

    def _get_incidents(self) -> list[IncidentDto]:
        # Skipping incidents pulling when we're installed with routing_key
        if self.authentication_config.routing_key:
            return []

        raw_incidents = self.__get_all_incidents_or_alerts()
        incidents = []
        for incident in raw_incidents:
            incident_dto = self._format_incident({"event": {"data": incident}})
            incident_alerts = self.__get_all_incidents_or_alerts(
                incident_id=incident_dto.fingerprint
            )
            incident_alerts = [self._format_alert(alert) for alert in incident_alerts]
            incident_dto._alerts = incident_alerts
            incidents.append(incident_dto)
        return incidents

    @staticmethod
    def _get_incident_id(incident_id: str) -> str:
        """
        Create a UUID from the incident id.

        Args:
            incident_id (str): The original incident id

        Returns:
            str: The UUID
        """
        md5 = hashlib.md5()
        md5.update(incident_id.encode("utf-8"))
        return uuid.UUID(md5.hexdigest())

    @staticmethod
    def _format_incident(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> IncidentDto | list[IncidentDto]:

        event = event["event"]["data"]

        # This will be the same for the same incident
        original_incident_id = event.get("id", "ping")

        incident_id = PagerdutyProvider._get_incident_id(original_incident_id)

        status = PagerdutyProvider.INCIDENT_STATUS_MAP.get(
            event.get("status", "firing"), IncidentStatus.FIRING
        )
        priority_summary = (event.get("priority", {}) or {}).get("summary", "P4")
        severity = PagerdutyProvider.INCIDENT_SEVERITIES_MAP.get(
            priority_summary, IncidentSeverity.INFO
        )
        service = event.pop("service", {}).get("summary", "unknown")

        created_at = event.get("created_at")
        if created_at:
            created_at = datetime.datetime.fromisoformat(created_at)
        else:
            created_at = datetime.datetime.now(tz=datetime.timezone.utc)

        return IncidentDto(
            id=incident_id,
            creation_time=created_at,
            user_generated_name=f'PD-{event.get("title", "unknown")}-{original_incident_id}',
            status=status,
            severity=severity,
            alert_sources=["pagerduty"],
            alerts_count=event.get("alert_counts", {}).get("all", 0),
            services=[service],
            is_predicted=False,
            is_confirmed=True,
            # This is the reference to the incident in PagerDuty
            fingerprint=original_incident_id,
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

    api_key = os.environ.get("PAGERDUTY_API_KEY")

    provider_config = {
        "authentication": {"api_key": api_key},
    }
    provider = ProvidersFactory.get_provider(
        context_manager=context_manager,
        provider_id="keep-pd",
        provider_type="pagerduty",
        provider_config=provider_config,
    )
    results = provider.setup_webhook(
        "keep",
        "https://eb8a-77-137-44-66.ngrok-free.app/alerts/event/pagerduty?provider_id=keep-pd",
        "https://eb8a-77-137-44-66.ngrok-free.app/incidents/event/pagerduty?provider_id=keep-pd",
        "just-a-test",
        True,
    )
