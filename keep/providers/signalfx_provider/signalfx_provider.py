import base64
import dataclasses
import datetime
from urllib.parse import quote, urlparse

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import (
    BaseProvider,
    ProviderConfig,
    ProviderScope,
)
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class SignalfxProviderAuthConfig:
    """
    Signalfx authentication configuration.
    """

    KEEP_SIGNALFX_WEBHOOK_INTEGRATION_NAME = "keep-signalfx-webhook-integration"

    sf_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "SignalFX token",
            "hint": "https://dev.splunk.com/observability/docs/administration/authtokens/",
            "sensitive": True,
        },
        default="",
    )
    realm: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SignalFX Realm",
            "sensitive": False,
            "hint": "https://api.{{realm}}.signalfx.com e.g. eu0",
        },
        default="eu0",
    )
    email: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SignalFX email. Required for setup webhook.",
            "sensitive": True,
            "hint": "https://dev.splunk.com/observability/reference/api/sessiontokens/latest",
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SignalFX password. Required for setup webhook.",
            "sensitive": True,
            "hint": "https://dev.splunk.com/observability/reference/api/sessiontokens/latest",
        },
        default="",
    )
    org_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "SignalFX organization ID. Required for setup webhook.",
            "sensitive": False,
            "hint": "https://dev.splunk.com/observability/reference/api/sessiontokens/latest",
        },
        default="",
    )


class SignalfxProvider(BaseProvider):
    """Get alerts from SignalFx into Keep."""

    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="API",
            description="API authScope - read permission for SignalFx API",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://dev.splunk.com/observability/reference/api/org_tokens/latest#endpoint-create-single-token",
            alias="API Read",
        ),
    ]
    PROVIDER_METHODS = []

    FINGERPRINT_FIELDS = ["detectorId", "incidentId"]
    PROVIDER_DISPLAY_NAME = "SignalFx"

    SEVERITIES_MAP = {
        "Critical": AlertSeverity.CRITICAL,
        "Major": AlertSeverity.HIGH,
        "Warning": AlertSeverity.WARNING,
        "Info": AlertSeverity.INFO,
        "Minor": AlertSeverity.LOW,
    }

    # https://docs.splunk.com/observability/en/admin/notif-services/webhook.html#observability-cloud-webhook-request-body-fields
    #   search for "statusExtended"
    STATUS_MAP = {
        "ok": AlertStatus.RESOLVED,
        "anomalous": AlertStatus.FIRING,
        "manually resolved": AlertStatus.RESOLVED,
        "stopped": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"https://api.{self.authentication_config.realm}.signalfx.com"
        self.api_token = self.authentication_config.sf_token
        if not self.api_token:
            raise ValueError("SignalFx token is required")

    def _get_headers(self):
        return {
            "X-SF-TOKEN": self.api_token,
            "Content-Type": "application/json",
        }

    def validate_scopes(self):
        # try to get some data from the API
        scopes = {}
        headers = self._get_headers()
        response = requests.get(f"{self.api_url}/v2/detector", headers=headers)
        try:
            response.raise_for_status()
            scopes["API"] = True
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Failed to get SignalFx alerts: {e.response.text}")
            scopes["API"] = str(e)
        return scopes

    def validate_config(self):
        self.authentication_config = SignalfxProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_alerts(self):
        headers = self._get_headers()
        # should also consider /v2/event/find but it looks like the same scehme
        #  https://dev.splunk.com/observability/reference/api/retrieve_events_v2/latest#endpoint-retrieve-events-using-query
        response = requests.get(f"{self.api_url}/v2/incident", headers=headers)
        response.raise_for_status()
        incidents = response.json()
        # Map SignalFx alert data to AlertDto objects
        alerts = []
        # TODO: incident may have more than one alert?
        for incident in incidents:
            try:
                alerts.append(self._format_alert_get_alert(incident))
            except Exception as e:
                self.logger.error(f"Failed to format SignalFx alert: {e}")
                pass

        return alerts

    @staticmethod
    def sanitize_url(url: str) -> str:
        # SignalFx URLs are not always properly formatted
        # e.g. 'https://app.eu0.signalfx.com/#/detector/YYYYYY/edit?incidentId=XXXXX&is=manually resolved'
        # so Pyatnadic will raise an error if the URL is not properly formatted

        # remove the # from the URL
        parsed_url = urlparse(url.replace("#", ""))
        # quote the query
        quoted_query = quote(parsed_url.query)
        # reassemble the URL
        url = url.replace(parsed_url.query, quoted_query)
        return url

    def _format_alert_get_alert(self, incident: dict) -> AlertDto:
        # there is difference between webhook payload (_format_alert)
        #   and alerts from API (get_alert) so we need to handle it separately
        last_alert = incident.get("events")[-1]
        severity = SignalfxProvider.SEVERITIES_MAP.get(
            incident.pop("severity").lower(), AlertSeverity.INFO
        )
        status = SignalfxProvider.STATUS_MAP.get(
            incident.pop("anomalyState").lower(), AlertStatus.FIRING
        )
        incident_id = incident.pop("incidentId")
        detector_id = incident.pop("detectorId")
        url = f"https://app.eu0.signalfx.com/#/detector/{detector_id}/edit?incidentId%3D{incident_id}"
        name = incident.pop("detectLabel")
        description = incident.pop("displayBody")
        lastReceived = datetime.datetime.fromtimestamp(
            last_alert.get("timestamp") / 1000
        ).isoformat()
        alert_dto = AlertDto(
            id=incident_id,
            name=name,
            description=description,
            lastReceived=lastReceived,
            severity=severity,
            status=status,
            url=url,
            source=["signalfx"],
            **incident,  # rest of the incident
        )
        alert_dto.fingerprint = SignalfxProvider.get_alert_fingerprint(
            alert_dto, SignalfxProvider.FINGERPRINT_FIELDS
        )
        return alert_dto

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # Transform a SignalFx event into an AlertDto object
        #   see: https://docs.splunk.com/observability/en/admin/notif-services/webhook.html#observability-cloud-webhook-request-body-fields
        severity = SignalfxProvider.SEVERITIES_MAP.get(
            event.pop("severity"), AlertSeverity.INFO
        )
        status = SignalfxProvider.STATUS_MAP.get(
            event.pop("statusExtended"), AlertStatus.FIRING
        )
        # remove the status so we won't have duplicated keywords
        event.pop("status", None)
        message = event.pop("messageBody", "")
        description = event.pop("description", "")
        name = event.pop("messageTitle", "")
        lastReceived = event.pop("timestamp", datetime.datetime.utcnow().isoformat())
        inputs: dict = event.pop("inputs", {})
        new_inputs = []
        for key, value in inputs.items():
            value["id"] = key
            new_inputs.append(value)
        event["inputs"] = new_inputs
        url = event.pop("detectorUrl")
        url = SignalfxProvider.sanitize_url(url)
        _id = event.pop("incidentId")
        alert_dto = AlertDto(
            id=_id,
            name=name,
            message=message,
            description=description,
            lastReceived=lastReceived,
            severity=severity,
            status=status,
            url=url,
            source=["signalfx"],
            **event,  # rest of the alert
        )
        alert_dto.fingerprint = SignalfxProvider.get_alert_fingerprint(
            alert_dto, SignalfxProvider.FINGERPRINT_FIELDS
        )
        return alert_dto

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        # see: https://dev.splunk.com/observability/reference/api/integrations/latest#endpoint-create-integration
        self.logger.info("Setting up SignalFx webhook integration")
        email = self.config.authentication.get("email")
        password = self.config.authentication.get("password")
        org_id = self.config.authentication.get("org_id")
        # all are required for webhook setup
        if not email or not password or not org_id:
            self.logger.error(
                "SignalFx email, password and organization ID are required for webhook setup"
            )
            return None
        # 1. First - get session token becuase to set up webhook
        #            you must have User API access token and you can use the Org access token
        #            https://dev.splunk.com/observability/reference/api/sessiontokens/latest
        headers = self._get_headers()
        session_payload = {
            "email": email,
            "password": password,
            "organizationId": org_id,
        }
        response = requests.post(
            f"{self.api_url}/v2/session",
            headers=headers,
            json=session_payload,
        )
        try:
            response.raise_for_status()
        # catch any HTTP errors
        except requests.exceptions.HTTPError as e:
            self.logger.error(
                f"Failed to get SignalFx session token: {e.response.text}"
            )
            return None
        # this is the token we need to setup the webhook
        # see: https://dev.splunk.com/observability/reference/api/sessiontokens/latest
        session_access_token = response.json().get("accessToken")
        # 2. Now let's check if the webhook integration already exists
        response = requests.get(f"{self.api_url}/v2/integration", headers=headers)
        try:
            response.raise_for_status()
        # catch any HTTP errors
        except requests.exceptions.HTTPError as e:
            self.logger.error(
                f"Failed to get SignalFx webhook integration: {e.response.text}"
            )
            return None

        integration_id = None
        integrations = response.json().get("results", [])
        for integration in integrations:
            # check if the webhook integration already exists
            if (
                integration.get("name")
                == SignalfxProviderAuthConfig.KEEP_SIGNALFX_WEBHOOK_INTEGRATION_NAME
            ):
                # the integration already exists, let's patch it
                self.logger.info("SignalFx webhook integration already exists")
                integration_id = integration.get("id")
                break

        auth_header = f"api_key:{api_key}"
        auth_header = base64.b64encode(auth_header.encode()).decode()
        webhook_payloads = {
            "name": SignalfxProviderAuthConfig.KEEP_SIGNALFX_WEBHOOK_INTEGRATION_NAME,
            "type": "Webhook",
            "enabled": True,
            "url": keep_api_url,
            # authentication with Keep api key
            "headers": {
                "Authorization": f"Basic {auth_header}",
            },
        }
        headers = {
            "X-SF-TOKEN": session_access_token,
        }
        # if integration_id is set, we need to update the existing integration
        if integration_id:
            # update the existing integration
            response = requests.put(
                f"{self.api_url}/v2/integration/{integration_id}",
                headers=headers,
                json=webhook_payloads,
            )
        else:
            response = requests.post(
                f"{self.api_url}/v2/integration",
                headers=headers,
                json=webhook_payloads,
            )
            # keep the integration id for later
            integration_id = response.json().get("id")
        try:
            response.raise_for_status()
        # catch any HTTP errors
        except requests.exceptions.HTTPError as e:
            self.logger.error(
                f"Failed to create SignalFx webhook integration: {e.response.text}"
            )
            return None
        self.logger.info("SignalFx webhook integration setup complete")
        # 3. Now subscribe webhook to all detectors
        #    https://docs.splunk.com/observability/en/admin/notif-services/webhook.html
        response = requests.get(f"{self.api_url}/v2/detector", headers=headers)
        try:
            response.raise_for_status()
        # catch any HTTP errors
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"Failed to get SignalFx detectors: {e.response.text}")
            return None
        detectors = response.json().get("results", [])
        # subscribe the webhook to all detectors
        for detector in detectors:
            self.logger.info(
                "Updating SignalFx detector",
                extra={
                    "detector_id": detector.get("id"),
                    "detector_name": detector.get("name"),
                },
            )
            detector_id = detector.get("id")
            rules = detector.get("rules", [])
            detector_updated = False
            for rule in rules:
                notifications = rule.get("notifications", [])
                keep_installed = integration_id in [
                    notification.get("credentialId") for notification in notifications
                ]
                if not keep_installed:
                    # add the webhook as a notification to the rule
                    self.logger.info(
                        "Adding SignalFx webhook to detector rule",
                        extra={
                            "rule_id": rule.get("id"),
                            "rule_name": rule.get("name"),
                        },
                    )
                    notifications.append(
                        {
                            "credentialId": integration_id,
                            "type": "Webhook",
                        }
                    )
                    detector_updated = True
            # if at least one rule was updated, update the detector
            if detector_updated:
                # update the detector
                #   https://dev.splunk.com/observability/reference/api/detectors/latest#endpoint-update-single-detector
                self.logger.info(
                    "Updating SignalFx detector",
                    extra={
                        "detector_id": detector_id,
                        "detector_name": detector.get("name"),
                    },
                )
                response = requests.put(
                    f"{self.api_url}/v2/detector/{detector_id}",
                    headers=headers,
                    json=detector,
                )
                try:
                    response.raise_for_status()
                    self.logger.info(
                        "SignalFx detector updated",
                        extra={
                            "detector_id": detector_id,
                            "detector_name": detector.get("name"),
                        },
                    )
                # catch any HTTP errors
                except requests.exceptions.HTTPError as e:
                    self.logger.error(
                        f"Failed to subscribe SignalFx detector {detector_id} to webhook: {e.response.text}"
                    )
                    return None
        self.logger.info("SignalFx webhook integration setup complete")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    realm = os.environ.get("SIGNALFX_REALM", "eu0")
    token = os.environ.get("SIGNALFX_TOKEN", "")
    email = os.environ.get("SIGNALFX_USER", "")
    password = os.environ.get("SIGNALFX_PASSWORD", "")
    org_id = os.environ.get("SIGNALFX_ORGID", "")
    keep_api_key = os.environ.get("KEEP_API_KEY")
    keep_api_url = os.environ.get("KEEP_API_URL")
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {
        "authentication": {
            "realm": realm,
            "sf_token": token,
            "email": email,
            "password": password,
            "org_id": org_id,
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="signalfx-keephq",
        provider_type="signalfx",
        provider_config=config,
    )
    webhook = provider.setup_webhook("keep", keep_api_url, keep_api_key, True)
    print(webhook)
