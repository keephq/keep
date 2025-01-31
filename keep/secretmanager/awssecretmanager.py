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
        try:
            session = boto3.session.Session()
            self.client = session.client(
                service_name="secretsmanager", region_name=os.environ.get("AWS_REGION")
            )
        except Exception as e:
            self.logger.error(
                "Failed to initialize AWS Secrets Manager client",
                extra={"error": str(e)},
            )
            raise

    def write_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Writes a secret to AWS Secrets Manager.
        Args:
            secret_name (str): The name of the secret.
            secret_value (str): The value of the secret.
        Raises:
            ClientError: If an AWS-specific error occurs while writing the secret.
            Exception: If any other unexpected error occurs.
        """
        with tracer.start_as_current_span("write_secret"):
            self.logger.info("Writing secret", extra={"secret_name": secret_name})

            try:
                # Check if secret exists by trying to describe it
                self.client.describe_secret(SecretId=secret_name)

                # If secret exists, update it with new value
                self.client.put_secret_value(
                    SecretId=secret_name, SecretString=secret_value
                )
                self.logger.info(
                    "Secret updated successfully", extra={"secret_name": secret_name}
                )
            except ClientError as e:
                if e.response["Error"]["Code"] == "ResourceNotFoundException":
                    try:
                        # Create new secret if it doesn't exist
                        self.client.create_secret(
                            Name=secret_name, SecretString=secret_value
                        )
                        self.logger.info(
                            "Secret created successfully",
                            extra={"secret_name": secret_name},
                        )
                    except Exception as e:
                        self.logger.error(
                            "Unexpected error while creating secret",
                            extra={
                                "secret_name": secret_name,
                                "error": str(e),
                                "error_type": type(e).__name__,
                            },
                        )
                        raise
                else:
                    self.logger.error(
                        "AWS error while writing secret",
                        extra={
                            "secret_name": secret_name,
                            "error": str(e),
                            "error_code": e.response["Error"]["Code"],
                        },
                    )
                    raise
            except Exception as e:
                self.logger.error(
                    "Unexpected error while writing secret",
                    extra={
                        "secret_name": secret_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise

    def read_secret(self, secret_name: str, is_json: bool = False) -> str | dict:
        """
        Reads a secret from AWS Secrets Manager.
        Args:
            secret_name (str): The name of the secret.
            is_json (bool): Whether to parse the secret as JSON. Defaults to False.
        Returns:
            str | dict: The secret value as a string, or as a dict if is_json=True.
        Raises:
            ClientError: If an AWS-specific error occurs while reading the secret.
            Exception: If any other unexpected error occurs.
        """
        with tracer.start_as_current_span("read_secret"):
            self.logger.debug("Getting secret", extra={"secret_name": secret_name})

            try:
                response = self.client.get_secret_value(SecretId=secret_name)
                secret_value = response["SecretString"]

                if is_json:
                    try:
                        secret_value = json.loads(secret_value)
                    except json.JSONDecodeError as e:
                        self.logger.error(
                            "Failed to parse secret as JSON",
                            extra={"secret_name": secret_name, "error": str(e)},
                        )
                        raise

                self.logger.debug(
                    "Got secret successfully", extra={"secret_name": secret_name}
                )
                return secret_value

            except ClientError as e:
                self.logger.error(
                    "AWS error while reading secret",
                    extra={
                        "secret_name": secret_name,
                        "error": str(e),
                        "error_code": e.response["Error"]["Code"],
                    },
                )
                raise
            except Exception as e:
                self.logger.error(
                    "Unexpected error while reading secret",
                    extra={
                        "secret_name": secret_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise

    def delete_secret(self, secret_name: str) -> None:
        """
        Deletes a secret from AWS Secrets Manager.
        Args:
            secret_name (str): The name of the secret.
        Raises:
            ClientError: If an AWS-specific error occurs while deleting the secret.
            Exception: If any other unexpected error occurs.
        """
        with tracer.start_as_current_span("delete_secret"):
            try:
                self.client.delete_secret(
                    SecretId=secret_name, ForceDeleteWithoutRecovery=True
                )
                self.logger.info(
                    "Secret deleted successfully", extra={"secret_name": secret_name}
                )
            except ClientError as e:
                self.logger.error(
                    "AWS error while deleting secret",
                    extra={
                        "secret_name": secret_name,
                        "error": str(e),
                        "error_code": e.response["Error"]["Code"],
                    },
                )
                raise
            except Exception as e:
                self.logger.error(
                    "Unexpected error while deleting secret",
                    extra={
                        "secret_name": secret_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise
