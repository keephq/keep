import json
import os

import opentelemetry.trace as trace
from google.api_core.exceptions import AlreadyExists
from google.cloud import secretmanager

from keep.secretmanager.secretmanager import BaseSecretManager

tracer = trace.get_tracer(__name__)


class GcpSecretManager(BaseSecretManager):
    def __init__(self, context_manager, **kwargs):
        super().__init__(context_manager)
        self.project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
        self.client = secretmanager.SecretManagerServiceClient()

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Writes a secret to the Secret Manager.

        Args:
            secret_name (str): The name of the secret.
            secret_value (str): The value of the secret.
        Raises:
            Exception: If an error occurs while writing the secret.
        """
        with tracer.start_as_current_span("write_secret"):
            self.logger.info("Writing secret", extra={"secret_name": secret_name})

            # Construct the resource name
            parent = f"projects/{self.project_id}"
            try:
                # Create the secret if it does not exist
                self.client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": {"replication": {"automatic": {}}},
                    }
                )
                self.logger.info(
                    "Secret created successfully", extra={"secret_name": secret_name}
                )
            except AlreadyExists:
                # If the secret already exists, update the existing secret version
                pass

            try:
                # Add the secret version.
                parent = self.client.secret_path(self.project_id, secret_name)
                payload_bytes = secret_value.encode("UTF-8")
                self.client.add_secret_version(
                    request={
                        "parent": parent,
                        "payload": {
                            "data": payload_bytes,
                        },
                    }
                )
                self.logger.info(
                    "Secret updated successfully", extra={"secret_name": secret_name}
                )
            except Exception as e:
                self.logger.error(
                    "Error writing secret",
                    extra={"secret_name": secret_name, "error": str(e)},
                )
                raise

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        with tracer.start_as_current_span("read_secret"):
            self.logger.debug("Getting secret", extra={"secret_name": secret_name})
            resource_name = (
                f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            )
            response = self.client.access_secret_version(name=resource_name)
            secret_value = response.payload.data.decode("UTF-8")
            if is_json:
                secret_value = json.loads(secret_value)
            self.logger.debug(
                "Got secret successfully", extra={"secret_name": secret_name}
            )
            return secret_value

    def delete_secret(self, secret_name: str) -> None:
        with tracer.start_as_current_span("delete_secret"):
            # Construct the resource name
            resource_name = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.delete_secret(request={"name": resource_name})
