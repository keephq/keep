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
    extraction: typing.Optional[list[dict[str, str]]] = dataclasses.field(
        default=None,
        metadata={
            "description": "Extraction Rules",
            "type": "form",
            "required": False,
            "hint": "Read more about extraction in Keep's Mailgun documentation",
        },
    )
    skip_dmarc_reports: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Skip DMARC reports",
            "hint": "Automatically skip DMARC aggregate reports",
            "type": "switch",
        },
    )
    skip_spf_reports: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Skip SPF reports",
            "hint": "Automatically skip SPF failure reports",
            "type": "switch",
        },
    )
    handle_emails_without_body: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Handle emails without body content",
            "hint": "Create alerts for emails that only have subject/attachments",
            "type": "switch",
        },
    )


class MailgunProvider(BaseProvider):
    MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY")
    MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "mails.keephq.dev")
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

        url = "https://api.mailgun.net/v3/routes"
        payload = {
            "priority": 0,
            "expression": expression,
            "description": f"Keep {self.provider_id} alerting",
            "action": [
                f"forward('{keep_api_url}&api_key={api_key}')",
                "stop()",
            ],
        }

        route_id = self.config.authentication.get("route_id")
        if route_id:
            response = requests.put(
                f"{url}/{self.config.authentication.get('route_id')}",
                files=payload,
                auth=("api", MailgunProvider.MAILGUN_API_KEY),
                data=payload,
            )
        else:
            response = requests.post(
                url,
                files=payload,
                auth=("api", MailgunProvider.MAILGUN_API_KEY),
                data=payload,
            )
        response.raise_for_status()
        response_json = response.json()
        route_id = route_id or response_json.get("route", {}).get("id")
        return {"route_id": route_id, "email": email}

    @staticmethod
    def _is_dmarc_report(event: dict) -> bool:
        """
        Detect DMARC reports using multiple indicators.
        
        Args:
            event: Email event data
            
        Returns:
            bool: True if email is a DMARC report
        """
        # Check sender patterns
        sender = event.get("from", "").lower()
        dmarc_senders = [
            "noreply-dmarc-support@google.com",
            "dmarc-support@google.com",
            "dmarc@",
            "postmaster@",
            "noreply@google.com"
        ]
        
        if any(dmarc_sender in sender for dmarc_sender in dmarc_senders):
            return True
        
        # Check subject patterns
        subject = event.get("subject", "").lower()
        if any(pattern in subject for pattern in ["report domain:", "dmarc", "aggregate report"]):
            return True
        
        # Check content type for ZIP attachments (DMARC reports are typically ZIP files)
        content_type = event.get("Content-Type", "").lower()
        if "application/zip" in content_type:
            return True
        
        # Check raw content if available
        raw_content = event.get("raw_content")
        if raw_content:
            if isinstance(raw_content, bytes) and b"dmarc" in raw_content.lower():
                return True
            elif isinstance(raw_content, str) and "dmarc" in raw_content.lower():
                return True
        
        return False

    @staticmethod
    def _is_spf_report(event: dict) -> bool:
        """
        Detect SPF failure reports.
        
        Args:
            event: Email event data
            
        Returns:
            bool: True if email is an SPF report
        """
        subject = event.get("subject", "").lower()
        sender = event.get("from", "").lower()
        
        spf_patterns = ["spf fail", "spf failure", "spf report", "sender policy framework"]
        return any(pattern in subject or pattern in sender for pattern in spf_patterns)

    @staticmethod
    def _is_bounce_notification(event: dict) -> bool:
        """
        Detect bounce notifications.
        
        Args:
            event: Email event data
            
        Returns:
            bool: True if email is a bounce notification
        """
        sender = event.get("from", "").lower()
        subject = event.get("subject", "").lower()
        
        bounce_senders = ["mailer-daemon@", "postmaster@", "bounce@"]
        bounce_patterns = ["delivery failed", "returned mail", "undelivered mail", "mail delivery"]
        
        return (
            any(bounce_sender in sender for bounce_sender in bounce_senders) or
            any(pattern in subject for pattern in bounce_patterns)
        )

    @staticmethod
    def _classify_email_type(event: dict) -> str:
        """
        Classify email type for appropriate handling.
        
        Args:
            event: Email event data
            
        Returns:
            str: Email type (dmarc_report, spf_report, bounce, alert)
        """
        if MailgunProvider._is_dmarc_report(event):
            return "dmarc_report"
        elif MailgunProvider._is_spf_report(event):
            return "spf_report"
        elif MailgunProvider._is_bounce_notification(event):
            return "bounce"
        else:
            return "alert"

    @staticmethod
    def _describe_attachments(event: dict) -> str:
        """
        Create a description of email attachments.
        
        Args:
            event: Email event data
            
        Returns:
            str: Description of attachments
        """
        attachment_count = event.get("attachment-count", "0")
        attachments = []
        
        # Try to get attachment info
        for i in range(1, int(attachment_count) + 1):
            attachment_key = f"attachment-{i}"
            if attachment_key in event:
                attachment_info = str(event[attachment_key])
                # Extract filename if possible
                if "filename=" in attachment_info:
                    filename = attachment_info.split("filename=")[1].split(",")[0].strip("'\"")
                    attachments.append(filename)
        
        if attachments:
            return f"{attachment_count} attachment(s): {', '.join(attachments)}"
        return f"{attachment_count} attachment(s)"

    @staticmethod
    def _extract_message_content(event: dict, email_type: str) -> str:
        """
        Extract message content based on email type.
        
        Args:
            event: Email event data
            email_type: Type of email (dmarc_report, spf_report, bounce, alert)
            
        Returns:
            str: Extracted message content
        """
        # Try standard body fields first
        message = event.get("stripped-text") or event.get("Body-plain")
        
        if message:
            return message
        
        # For DMARC reports, use subject as message
        if email_type == "dmarc_report":
            subject = event.get("subject", "")
            if subject:
                return f"DMARC Report: {subject}"
        
        # For emails with attachments, describe the attachment
        if event.get("attachment-count") and int(event.get("attachment-count", 0)) > 0:
            attachment_info = MailgunProvider._describe_attachments(event)
            subject = event.get("subject", "")
            if subject:
                return f"{subject} ({attachment_info})"
            return f"Email with {attachment_info}"
        
        # Fallback to subject
        subject = event.get("subject", "")
        if subject:
            return subject
        
        return "No message content available"

    @staticmethod
    def _log_email_processing(event: dict, email_type: str, action: str):
        """
        Enhanced logging for email processing.
        
        Args:
            event: Email event data
            email_type: Type of email
            action: Action taken (skipped, processed, etc.)
        """
        logger.info(
            f"Email processing: {action}",
            extra={
                "email_type": email_type,
                "from": event.get("from"),
                "subject": event.get("subject"),
                "has_body": bool(event.get("Body-plain") or event.get("stripped-text")),
                "has_attachments": bool(event.get("attachment-count")),
                "content_type": event.get("Content-Type"),
                "action": action
            }
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "MailgunProvider" = None
    ) -> AlertDto:
        """
        Format email event into an AlertDto.
        
        Args:
            event: Email event data
            provider_instance: Optional MailgunProvider instance for config access
            
        Returns:
            AlertDto or None if email should be skipped
        """
        try:
            # We receive FormData here, convert it to simple dict.
            logger.info(
                "Received alert from mail",
                extra={
                    "from": event.get("from"),
                    "subject": event.get("subject")
                },
            )
            event = dict(event)

            # Classify email type first
            email_type = MailgunProvider._classify_email_type(event)
            
            # Check provider instance configuration for skip settings
            skip_dmarc = True  # Default
            skip_spf = True  # Default
            handle_no_body = True  # Default
            
            if provider_instance and hasattr(provider_instance, 'authentication_config'):
                skip_dmarc = getattr(provider_instance.authentication_config, 'skip_dmarc_reports', True)
                skip_spf = getattr(provider_instance.authentication_config, 'skip_spf_reports', True)
                handle_no_body = getattr(provider_instance.authentication_config, 'handle_emails_without_body', True)
            
            # Handle DMARC reports
            if email_type == "dmarc_report" and skip_dmarc:
                MailgunProvider._log_email_processing(event, email_type, "skipped (DMARC report)")
                return None
            
            # Handle SPF reports
            if email_type == "spf_report" and skip_spf:
                MailgunProvider._log_email_processing(event, email_type, "skipped (SPF report)")
                return None
            
            # Handle bounce notifications (optionally skip)
            if email_type == "bounce":
                MailgunProvider._log_email_processing(event, email_type, "processing (bounce notification)")

            # Extract basic fields
            source = event.get("from", "unknown@unknown.com")
            name = event.get("subject", source)
            
            # Extract message content with fallback logic
            message = MailgunProvider._extract_message_content(event, email_type)
            
            # Validate required fields with flexible handling
            if not name:
                name = source or "Unknown Email"
                logger.warning(
                    "Email has no subject, using source as name",
                    extra={"from": source, "email_type": email_type}
                )
            
            if not message:
                if handle_no_body:
                    message = f"Email from {source} (no body content)"
                    logger.warning(
                        "Email has no body content, using fallback message",
                        extra={"from": source, "subject": name, "email_type": email_type}
                    )
                else:
                    MailgunProvider._log_email_processing(event, email_type, "skipped (no body content)")
                    return None

            # Extract timestamp
            try:
                timestamp = datetime.datetime.fromtimestamp(
                    float(event["timestamp"])
                ).isoformat()
            except Exception:
                timestamp = datetime.datetime.now().isoformat()
            
            # Default values
            severity = "info"
            status = "firing"

            # Clean redundant fields
            event.pop("signature", None)
            event.pop("token", None)

            MailgunProvider._log_email_processing(event, email_type, "processing")

            # Create alert
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

            # Add all attributes from raw_email to the alert dto, except the ones that are already set
            for key, value in event.items():
                # Avoid "-" in keys cuz CEL will fail [stripped-text screw CEL]
                if not hasattr(alert, key) and "-" not in key:
                    setattr(alert, key, value)

            # Add email type as metadata
            setattr(alert, "email_type", email_type)

            logger.info("Alert formatted", extra={"email_type": email_type, "alert_name": name})

            # Apply extraction rules if configured
            if provider_instance:
                logger.info("Provider instance found")
                extraction_rules = provider_instance.authentication_config.extraction
                if extraction_rules:
                    logger.info("Extraction rules found")
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
            
            logger.info("Alert extracted successfully", extra={"email_type": email_type})
            return alert
            
        except KeyError as e:
            logger.error(
                f"Missing required field in email event: {e}",
                extra={
                    "event_keys": list(event.keys()),
                    "missing_field": str(e)
                }
            )
            raise
        except Exception as e:
            logger.error(
                f"Error formatting alert from email: {e}",
                extra={
                    "event_keys": list(event.keys()),
                    "from": event.get("from"),
                    "subject": event.get("subject"),
                    "error": str(e)
                }
            )
            raise


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
