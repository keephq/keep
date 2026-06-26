import dataclasses
import datetime
import logging
import os
import re
import typing

import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class MailgunProviderAuthConfig:
    email: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Email address to send alerts to",
            "sensitive": False,
            "hint": "This will get populated automatically after installation",
            "readOnly": True,
        },
        default="",
    )
    sender: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Sender email address to validate",
            "hint": ".*@keephq.dev for example, leave empty for any.",
        },
        default="",
    )
    email_domain: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Custom email domain for receiving alerts",
            "hint": "e.g., alerts.yourcompany.com (uses env MAILGUN_DOMAIN if not set)",
            "sensitive": False,
        },
        default="",
    )
    api_region: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Mailgun API region",
            "hint": "Select 'US' for api.mailgun.net or 'EU' for api.eu.mailgun.net (uses env MAILGUN_REGION if not set)",
            "sensitive": False,
            "type": "select",
            "options": ["US", "EU"],
        },
        default="",
    )
    extraction: typing.Optional[list[dict[str, str]]] = dataclasses.field(
        default=None,
        metadata={
            "description": "Extraction Rules",
            "type": "form",
            "required": False,
            "hint": "Read more about extraction in Keep's Mailgun documentation",
        },
    )


class MailgunProvider(BaseProvider):
    MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "mails.keephq.dev")
    MAILGUN_REGION = os.environ.get("MAILGUN_REGION", "US")  # US or EU
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ) -> None:
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MailgunProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    @staticmethod
    def parse_event_raw_body(raw_body: bytes | dict) -> dict:
        """
        Parse the raw body of a Mailgun webhook event and create an ingestable dict.

        Args:
            raw_body (bytes | dict): The raw body from the webhook

        Returns:
            dict: Parsed event data in a format compatible with _format_alert
        """
        if not isinstance(raw_body, bytes):
            return raw_body

        logger.info("Parsing Mail Body")
        try:
            # Use latin1 as it can handle any byte sequence
            content = raw_body.decode("latin1", errors="replace")
            parsed_data = {}

            # Try to find body-plain content
            if 'Content-Disposition: form-data; name="body-plain"' in content:
                logger.info("Mail Body Found")
                # Extract body-plain content
                parts = content.split(
                    'Content-Disposition: form-data; name="body-plain"'
                )
                if len(parts) > 1:
                    body_content = parts[1].split("\r\n\r\n", 1)[1].split("\r\n--")[0]

                    # Convert the alert format to Mailgun expected format
                    parsed_data = {
                        "subject": "",  # Will be populated below
                        "from": "",  # Will be populated from Source
                        "stripped-text": "",  # Will be populated from message content
                        "timestamp": "",  # Will be populated from Opened
                    }

                    # Parse the content line by line
                    for line in body_content.strip().splitlines():
                        if ":" in line:
                            key, value = line.split(":", 1)
                            key = key.strip()
                            value = value.strip()

                            # Map the fields to what _format_alert expects
                            if key == "Summary":
                                parsed_data["subject"] = value
                            elif key == "Source":
                                parsed_data["from"] = value
                            elif key in ["Alert Status", "Severity"]:
                                parsed_data[key.lower()] = value
                            elif key == "Opened":
                                # Convert the date format to timestamp
                                try:
                                    dt = datetime.datetime.strptime(
                                        value, "%d %b %Y %H:%M UTC"
                                    )
                                    parsed_data["timestamp"] = str(dt.timestamp())
                                except ValueError:
                                    parsed_data["timestamp"] = str(
                                        datetime.datetime.now().timestamp()
                                    )
                            else:
                                parsed_data[key.lower()] = value

                    # Combine relevant fields for the message
                    message_parts = []
                    for key in [
                        "Summary",
                        "Alert Category",
                        "Service Test",
                        "Severity",
                        "Alert Status",
                    ]:
                        if key in body_content:
                            for line in body_content.split("\r\n"):
                                if line.startswith(key + ":"):
                                    message_parts.append(line)

                    parsed_data["stripped-text"] = "\n".join(message_parts)

                    # Store the full original content
                    parsed_data["raw_content"] = body_content
                    logger.info("Mail Body Parsed", extra={"parsed_data": parsed_data})
                    return parsed_data
            logger.info("Mail Body Not Found")
            return {
                "subject": "Unknown Alert",
                "from": "system@keep",
                "stripped-text": content,
            }

        except Exception as e:
            logger.exception(f"Error parsing webhook body: {e}")
            return {
                "subject": "Error Processing Alert",
                "from": "system",
                "stripped-text": "Error processing the alert content",
                "timestamp": str(datetime.datetime.now().timestamp()),
            }

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ) -> dict[str, str]:
        if not MailgunProvider.MAILGUN_API_KEY:
            raise Exception("MAILGUN_API_KEY is not set")

        # Use custom domain from config, env var, or default
        email_domain = (
            self.authentication_config.email_domain 
            or MailgunProvider.MAILGUN_DOMAIN
        )
        
        email = f"{tenant_id}-{self.provider_id}@{email_domain}"
        expression = f'match_recipient("{email}")'

        if (
            "match_header" in self.authentication_config.sender
            or "match_recipient" in self.authentication_config.sender
        ):  # validate that somebody doesn't try to use match_header or match_recipient
            raise ValueError("Invalid sender value")
        if self.authentication_config.sender:
            sender = self.authentication_config.sender
            # Bob <bob@example.com>
            if not sender.startswith(".*"):
                sender = f".*{sender}"
            if not sender.endswith(">"):
                sender = f"{sender}>"
            expression = f'({expression} and match_header("from", "{sender}"))'

        # Use correct API endpoint based on region (UI field takes priority, then env variable)
        region = (
            self.authentication_config.api_region 
            or MailgunProvider.MAILGUN_REGION
            or "US"
        ).upper()
        api_base = "https://api.mailgun.net" if region == "US" else "https://api.eu.mailgun.net"
        url = f"{api_base}/v3/routes"
        
        # Mailgun expects form data with multiple action fields
        payload = {
            "priority": 0,
            "expression": expression,
            "description": f"Keep {self.provider_id} alerting",
        }

        route_id = self.config.authentication.get("route_id")
        if route_id:
            # Update existing route
            response = requests.put(
                f"{url}/{route_id}",
                auth=("api", MailgunProvider.MAILGUN_API_KEY),
                data={
                    **payload,
                    "action": [
                        f"forward('{keep_api_url}&api_key={api_key}')",
                        "stop()",
                    ],
                },
            )
        else:
            # Create new route
            response = requests.post(
                url,
                auth=("api", MailgunProvider.MAILGUN_API_KEY),
                data={
                    **payload,
                    "action": [
                        f"forward('{keep_api_url}&api_key={api_key}')",
                        "stop()",
                    ],
                },
            )
        response.raise_for_status()
        response_json = response.json()
        route_id = route_id or response_json.get("route", {}).get("id")
        return {"route_id": route_id, "email": email}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "MailgunProvider" = None
    ) -> AlertDto:
        # We receive FormData here, convert it to simple dict.
        logger.info(
            "Received alert from mail",
            extra={
                "from": event["from"],
                "subject": event.get("subject")
            },
        )
        event = dict(event)

        source = event["from"]
        name = event.get("subject", source)
        body_plain = event.get("Body-plain")
        message = event.get("stripped-text", body_plain)
        raw_content = event.get("raw_content")

        if isinstance(raw_content, bytes) and b"dmarc" in raw_content.lower():
            logger.warning("DMARC alert detected, skipping")
            return None
        elif isinstance(raw_content, str) and "dmarc" in raw_content.lower():
            logger.warning("DMARC alert detected, skipping")
            return None

        if not name or not message:
            raise Exception(
                "Could not create alert from email when name or message is missing."
            )

        try:
            timestamp = datetime.datetime.fromtimestamp(
                float(event["timestamp"])
            ).isoformat()
        except Exception:
            timestamp = datetime.datetime.now().isoformat()
        # default values
        severity = "info"
        status = "firing"

        # clean redundant
        event.pop("signature", "")
        event.pop("token", "")

        logger.info("Basic formatting done")

        alert = AlertDto(
            name=name,
            source=[source],
            message=message,
            description=message,
            lastReceived=timestamp,
            severity=severity,
            status=status,
            raw_email={**event},
        )

        # now I want to add all attributes from raw_email to the alert dto, except the ones that are already set
        for key, value in event.items():
            # avoid "-" in keys cuz CEL will failed [stripped-text screw CEL]
            if not hasattr(alert, key) and "-" not in key:
                setattr(alert, key, value)

        logger.info(
            "Alert formatted",
        )

        if provider_instance:
            logger.info(
                "Provider instance found",
            )
            extraction_rules = provider_instance.authentication_config.extraction
            if extraction_rules:
                logger.info(
                    "Extraction rules found",
                )
                for rule in extraction_rules:
                    key = rule.get("key")
                    regex = rule.get("value")
                    if key in dict(event):
                        try:
                            match = re.search(regex, event[key])
                            if match:
                                for (
                                    group_name,
                                    group_value,
                                ) in match.groupdict().items():
                                    setattr(alert, group_name, group_value)
                        except Exception as e:
                            logger.exception(
                                f"Error extracting key {key} with regex {regex}: {e}",
                                extra={
                                    "provider_id": provider_instance.provider_id,
                                    "tenant_id": provider_instance.context_manager.tenant_id,
                                },
                            )
        logger.info(
            "Alert extracted",
        )
        return alert


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Initalize the provider and provider config
    config = {
        "description": "Console Output Provider",
        "authentication": {},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="mock",
        provider_type="console",
        provider_config=config,
    )
    provider.notify(alert_message="Simple alert showing context with name: John Doe")
