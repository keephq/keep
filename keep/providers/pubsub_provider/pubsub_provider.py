"""
Google Cloud Pub/Sub provider for Keep.
"""
import dataclasses
import json
import os
from typing import Optional, Dict, Any

import pydantic
from google.cloud import pubsub_v1
from google.oauth2 import service_account
from google.api_core import retry, exceptions

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PubsubProviderAuthConfig:
    """Pub/Sub authentication configuration."""
    
    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The service account JSON with pubsub.publisher role",
            "sensitive": True,
            "type": "file",
            "name": "service_account_json",
            "file_type": ".json",
        },
    )
    project_id: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Google Cloud project ID. If not provided, "
            "it will try to fetch it from the environment variable 'GOOGLE_CLOUD_PROJECT'",
        },
    )
    topic_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The Pub/Sub topic ID to publish messages to",
        },
        default="",
    )

class PubsubProvider(BaseProvider):
    """Send messages to Google Cloud Pub/Sub."""

    PROVIDER_DISPLAY_NAME = "Google Cloud Pub/Sub"
    PROVIDER_TAGS = ["messaging", "queue"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.publisher = None
        self.topic_path = None

    def validate_config(self):
        """Validates the provider configuration."""
        self.authentication_config = PubsubProviderAuthConfig(
            **self.config.authentication
        )
        if not all([
            self.authentication_config.project_id,
            self.authentication_config.topic_id,
            self.authentication_config.service_account_json
        ]):
            raise Exception("All PubSub authentication parameters are required")

    def init_client(self):
        """Initialize the Pub/Sub client if not already initialized."""
        if not self.publisher:
            try:
                if self.authentication_config.service_account_json:
                    # Check if the input is a file path or JSON content
                    if os.path.isfile(self.authentication_config.service_account_json):
                        self.publisher = pubsub_v1.PublisherClient.from_service_account_json(
                            self.authentication_config.service_account_json
                        )
                    else:
                        # Handle JSON content directly
                        credentials = service_account.Credentials.from_service_account_info(
                            json.loads(self.authentication_config.service_account_json)
                        )
                        self.publisher = pubsub_v1.PublisherClient(credentials=credentials)
                else:
                    self.publisher = pubsub_v1.PublisherClient()

                # Set project ID from config or environment
                project_id = self.authentication_config.project_id
                if not project_id:
                    try:
                        project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
                    except KeyError:
                        raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set.")

                self.topic_path = self.publisher.topic_path(
                    project_id,
                    self.authentication_config.topic_id
                )

            except Exception as e:
                self.logger.error(
                    "Failed to initialize Pub/Sub client",
                    extra={"error": str(e)}
                )
                raise

    def dispose(self):
        """Clean up resources."""
        if self.publisher:
            self.publisher.close()

    @retry.Retry()
    def _notify(self, alert=None, message=None, title=None, **kwargs):
        """
        Publish a message to Pub/Sub.
        
        Args:
            alert (dict, optional): Alert data to publish
            message (str/dict, optional): Message to publish
            title (str, optional): Title for the message
            **kwargs: Additional arguments to pass to the publisher
        """
        self.init_client()
        self._ensure_topic_exists()

        # Determine what to publish
        if alert:
            data = json.dumps(alert if isinstance(alert, dict) else {"message": str(alert)})
            attributes = {
                "alert_id": str(alert.get("id", "")) if isinstance(alert, dict) else "",
                "severity": str(alert.get("severity", "")) if isinstance(alert, dict) else "",
                "source": str(alert.get("source", "")) if isinstance(alert, dict) else "",
                "provider_id": self.provider_id
            }
        else:
            data = message if isinstance(message, str) else json.dumps(message or {})
            attributes = {
                "title": str(title or ""),
                "provider_id": self.provider_id
            }

        # Encode data for Pub/Sub
        data = data.encode("utf-8")

        try:
            future = self.publisher.publish(
                self.topic_path,
                data,
                **attributes
            )
            message_id = future.result()
            
            self.logger.info(
                f"Published message to {self.topic_path}",
                extra={
                    "message_id": message_id,
                    "topic": self.topic_path,
                    "provider_id": self.provider_id
                }
            )
            
            return {"message_id": message_id, "topic": self.topic_path}
            
        except Exception as e:
            self.logger.error(
                "Failed to publish message to Pub/Sub",
                extra={
                    "error": str(e),
                    "topic": self.topic_path,
                    "provider_id": self.provider_id
                }
            )
            raise

    def _query(self, **kwargs):
        """Not implemented for Pub/Sub provider."""
        raise NotImplementedError("Query operation not supported for Pub/Sub provider")

    def get_alerts_configuration(self, alert_id: Optional[str] = None):
        """Not implemented for Pub/Sub provider."""
        pass

    def deploy_alert(self, alert: dict, alert_id: Optional[str] = None):
        """Not implemented for Pub/Sub provider."""
        pass

    def _ensure_topic_exists(self):
        """Create the topic if it doesn't exist."""
        try:
            self.logger.info(f"Checking if topic {self.topic_path} exists")
            self.publisher.get_topic(request={"topic": self.topic_path})
        except exceptions.NotFound:
            try:
                self.publisher.create_topic(request={"name": self.topic_path})
                self.logger.info(f"Created topic {self.topic_path}")
            except Exception as create_error:
                self.logger.error(
                    "Failed to create topic",
                    extra={"error": str(create_error), "topic": self.topic_path}
                )
                raise
        except Exception as e:
            self.logger.error(
                "Failed to check if topic exists",
                extra={"error": str(e), "topic": self.topic_path}
            )
            raise
