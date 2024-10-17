import json
import os

import boto3
import opentelemetry.trace as trace
from botocore.exceptions import ClientError
from keep.secretmanager.secretmanager import BaseSecretManager

tracer = trace.get_tracer(__name__)


class AwsSecretManager(BaseSecretManager):
    def __init__(self, context_manager, **kwargs):
        super().__init__(context_manager)
        # Create a Secrets Manager client using boto3 session
        session = boto3.session.Session()
        self.client = session.client(
            service_name="secretsmanager", region_name=os.environ.get("AWS_REGION")
        )

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Writes a secret to AWS Secrets Manager.
        Args:
            secret_name (str): The name of the secret.
            secret_value (str): The value of the secret.
        Raises:
            Exception: If an error occurs while writing the secret.
        """
        with tracer.start_as_current_span("write_secret"):
            self.logger.info("Writing secret", extra={"secret_name": secret_name})

            try:
                # Check if the secret already exists
                self.client.describe_secret(SecretId=secret_name)

                # If the secret exists, update its value
                self.client.put_secret_value(
                    SecretId=secret_name, SecretString=secret_value
                )
                self.logger.info(
                    "Secret updated successfully", extra={"secret_name": secret_name}
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    # If the secret does not exist, create a new secret
                    try:
                        self.client.create_secret(
                            Name=secret_name, SecretString=secret_value
                        )
                        self.logger.info(
                            "Secret created successfully",
                            extra={"secret_name": secret_name},
                        )
                    except ClientError as create_error:
                        self.logger.error(
                            "Error creating secret",
                            extra={
                                "secret_name": secret_name,
                                "error": str(create_error),
                            },
                        )
                        raise create_error
                else:
                    self.logger.error(
                        "Error writing secret",
                        extra={"secret_name": secret_name, "error": str(e)},
                    )
                    raise e

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        """
        Reads a secret from AWS Secrets Manager.
        Args:
            secret_name (str): The name of the secret.
            is_json (bool): Whether to parse the secret as JSON. Defaults to False.
        Returns:
            str | dict: The secret value.
        """
        with tracer.start_as_current_span("read_secret"):
            self.logger.debug("Getting secret", extra={"secret_name": secret_name})

            try:
                get_secret_value_response = self.client.get_secret_value(
                    SecretId=secret_name
                )
                secret_value = get_secret_value_response.get("SecretString")

                if is_json:
                    secret_value = json.loads(secret_value)

                self.logger.debug(
                    "Got secret successfully", extra={"secret_name": secret_name}
                )
                return secret_value
            except ClientError as e:
                self.logger.error(
                    "Error reading secret",
                    extra={"secret_name": secret_name, "error": str(e)},
                )
                raise e

    def delete_secret(self, secret_name: str) -> None:
        """
        Deletes a secret from AWS Secrets Manager.
        Args:
            secret_name (str): The name of the secret.
        Raises:
            Exception: If an error occurs while deleting the secret.
        """
        with tracer.start_as_current_span("delete_secret"):
            try:
                # Forcefully delete the secret without recovery
                self.client.delete_secret(
                    SecretId=secret_name, ForceDeleteWithoutRecovery=True
                )
                self.logger.info(
                    "Secret deleted successfully", extra={"secret_name": secret_name}
                )
            except ClientError as e:
                self.logger.error(
                    "Error deleting secret",
                    extra={"secret_name": secret_name, "error": str(e)},
                )
                raise e
