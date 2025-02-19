"""
S3 Provider for querying S3 buckets.
"""

import dataclasses

import boto3
import pydantic

from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider


@pydantic.dataclasses.dataclass
class S3ProviderAuthConfig:
    access_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "S3 Access Token (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        },
        default=None,
    )

    secret_access_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "S3 Secret Access Token (Leave empty if using IAM role at EC2)",
            "sensitive": True,
        },
        default=None,
    )


class S3Provider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "AWS S3"
    PROVIDER_CATEGORY = ["Cloud Infrastructure"]

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = S3ProviderAuthConfig(**self.config.authentication)
        if (
            self.authentication_config.access_key is None
            or self.authentication_config.secret_access_key is None
        ):
            raise ProviderException("Access key and secret access key are required")
        boto3.client(
            "s3",
            aws_access_key_id=self.authentication_config.access_key,
            aws_secret_access_key=self.authentication_config.secret_access_key,
        )
        # List all S3 buckets to validate the credentials
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.authentication_config.access_key,
            aws_secret_access_key=self.authentication_config.secret_access_key,
        )
        try:
            s3_client.list_buckets()
        except Exception as e:
            raise ProviderException(f"Failed to list S3 buckets: {e}")

    def _query(self, bucket: str, **kwargs: dict):
        """
        Query bucket for files. Downdload only yaml, json, xml and csv files.

        Returns:
            list[file_content]: results the list of downloaded files
        """
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=self.authentication_config.access_key,
            aws_secret_access_key=self.authentication_config.secret_access_key,
        )
        try:
            response = s3_client.list_objects_v2(Bucket=bucket)
        except Exception as e:
            raise ProviderException(f"Failed to list objects in bucket: {e}")
        files = []
        for obj in response.get("Contents", []):
            key = obj.get("Key")
            valid_extensions = [".yaml", ".json", ".xml", ".csv", ".yml"]
            if any(key.endswith(ext) for ext in valid_extensions):
                try:
                    response = s3_client.get_object(Bucket=bucket, Key=key)
                    files.append(response.get("Body").read().decode("utf-8"))
                    print(files)
                except Exception as e:
                    self.logger.exception(
                        "Failed to download object from S3: %s", str(e)
                    )
        return files
