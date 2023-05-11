import json
import os

from google.cloud import secretmanager

from keep.secretmanager.secretmanager import BaseSecretManager


class GcpSecretManager(BaseSecretManager):
    def __init__(self, **kwargs):
        super().__init__()
        self.project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
        self.client = secretmanager.SecretManagerServiceClient()

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        return super().write_secret(secret_name, secret_value)

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        self.logger.info("Getting secret", extra={"secret_name": secret_name})
        resource_name = (
            f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
        )
        response = self.client.access_secret_version(name=resource_name)
        secret_value = response.payload.data.decode("UTF-8")
        if is_json:
            secret_value = json.loads(secret_value)
        self.logger.info("Got secret successfully", extra={"secret_name": secret_name})
        return secret_value
