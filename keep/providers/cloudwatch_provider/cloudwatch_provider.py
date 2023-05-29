"""
CloudwatchProvider is a class that provides a way to read data from AWS Cloudwatch.
"""

import dataclasses
import datetime
import os
import time

import boto3
import pydantic

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CloudwatchProviderAuthConfig:
    access_key: str = dataclasses.field(
        metadata={"required": True, "description": "AWS access key", "sensitive": True}
    )
    access_key_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AWS access key secret",
            "sensitive": True,
        }
    )
    region: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "AWS region",
        },
        default="us-west-2",
    )


class CloudwatchProvider(BaseProvider):
    """
    CloudwatchProvider is a class that provides a way to read data from AWS Cloudwatch.
    """

    def __init__(self, aws_client_type: str, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        self.client = self.__generate_client(aws_client_type)

    def __generate_client(self, aws_client_type: str):
        client = boto3.client(
            aws_client_type,
            aws_access_key_id=self.authentication_config.access_key,
            aws_secret_access_key=self.authentication_config.access_key_secret,
            region_name=self.authentication_config.region,
        )
        return client

    def dispose(self):
        try:
            self.client.close()
        except Exception:
            self.logger.exception("Error closing boto3 connection")

    def validate_config(self):
        self.authentication_config = CloudwatchProviderAuthConfig(
            **self.config.authentication
        )


class CloudwatchLogsProvider(CloudwatchProvider):
    """
    CloudwatchLogsProvider is a class that provides a way to read data from AWS Cloudwatch Logs.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__("logs", provider_id, config)

    def query(self, **kwargs: dict) -> dict:
        log_group = kwargs.get("log_group")
        query = kwargs.get("query")
        hours = kwargs.get("hours", 24)
        start_query_response = self.client.start_query(
            logGroupName=log_group,
            queryString=query,
            startTime=int(
                (
                    datetime.datetime.today() - datetime.timedelta(hours=hours)
                ).timestamp()
            ),
            endTime=int(datetime.datetime.now().timestamp()),
        )

        query_id = start_query_response["queryId"]

        response = None

        while response is None or response["status"] == "Running":
            self.logger.debug("Waiting for AWS cloudwatch query to complete...")
            time.sleep(1)
            response = self.client.get_query_results(queryId=query_id)

        return results


class CloudwatchMetricsProvider(CloudwatchProvider):
    """
    CloudwatchMetricsProvider is a class that provides a way to read data from AWS Cloudwatch Metrics.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__("cloudwatch", provider_id, config)

    def query(self, **kwargs: dict) -> None:
        raise NotImplementedError(
            'CloudwatchMetricsProvider does not support "query" method yet.'
        )


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "access_key_secret": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        }
    )
    cloudwatch_provider = CloudwatchMetricsProvider("cloudwatch-prod", config)
    results = cloudwatch_provider.query(
        query="fields @timestamp, @message, @logStream, @log | sort @timestamp desc | limit 20",
        log_group="Test",
    )
    print(results)
