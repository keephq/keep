"""
CloudwatchProvider is a class that provides a way to read data from AWS Cloudwatch.
"""

import dataclasses
import datetime
import hashlib
import json
import logging
import os
import random
import time
from urllib.parse import urlparse

import boto3
import pydantic
import requests

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
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
            "required": True,
            "description": "AWS region",
        },
    )
    session_token: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS Session Token",
            "hint": "For temporary credentials. Note that if you connect CloudWatch with temporary credentials, the initial connection will succeed, but when the credentials expired alarms won't be sent to Keep.",
            "sensitive": True,
        },
    )
    cloudwatch_sns_topic: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "AWS Cloudwatch SNS Topic [ARN or name]",
            "hint": "Default SNS Topic to send notifications (Optional since if your alarms already sends notifications to SNS topic, Keep will use the exists SNS topic)",
            "sensitive": False,
        },
    )


class CloudwatchProvider(BaseProvider):
    """
    CloudwatchProvider is a class that provides a way to read data from AWS Cloudwatch.
    """

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.aws_client_type = None
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self.client = self.__generate_client(self.aws_client_type)
        return self._client

    def _get_account_id(self):
        sts_client = self.__generate_client("sts")
        identity = sts_client.get_caller_identity()
        return identity["Account"]

    def __generate_client(self, aws_client_type: str):
        if self.authentication_config.session_token:
            self.logger.info("Using temporary credentials")
            client = boto3.client(
                aws_client_type,
                aws_access_key_id=self.authentication_config.access_key,
                aws_secret_access_key=self.authentication_config.access_key_secret,
                aws_session_token=self.authentication_config.session_token,
                region_name=self.authentication_config.region,
            )
        else:
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

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        # first, list all Cloudwatch alarms
        self.logger.info("Setting up webhook with url %s", keep_api_url)
        cloudwatch_client = self.__generate_client("cloudwatch")
        sns_client = self.__generate_client("sns")
        resp = cloudwatch_client.describe_alarms()
        alarms = resp.get("MetricAlarms", [])
        alarms.extend(resp.get("CompositeAlarms"))
        subscribed_topics = []
        # for each alarm, we need to iterate the actions topics and subscribe to them
        for alarm in alarms:
            actions = alarm.get("AlarmActions", [])
            # extract only SNS actions
            topics = [action for action in actions if action.startswith("arn:aws:sns")]
            # if not topics but the user supplied fallback cloudwatch_sns_topic
            if not topics and self.authentication_config.cloudwatch_sns_topic:
                self.logger.warning(
                    "Cannot hook alarm without SNS topic, trying to add SNS action..."
                )
                # add an action to the alarm
                if not self.authentication_config.cloudwatch_sns_topic.startswith(
                    "arn:aws:sns"
                ):
                    account_id = self._get_account_id()
                    sns_topic = f"arn:aws:sns:{self.authentication_config.region}:{account_id}:{self.authentication_config.cloudwatch_sns_topic}"
                else:
                    sns_topic = self.authentication_config.cloudwatch_sns_topic
                actions.append(sns_topic)
                try:
                    alarm["AlarmActions"] = actions
                    # filter out irrelevant files
                    valid_keys = {
                        "AlarmName",
                        "AlarmDescription",
                        "ActionsEnabled",
                        "OKActions",
                        "AlarmActions",
                        "InsufficientDataActions",
                        "MetricName",
                        "Namespace",
                        "Statistic",
                        "ExtendedStatistic",
                        "Dimensions",
                        "Period",
                        "Unit",
                        "EvaluationPeriods",
                        "DatapointsToAlarm",
                        "Threshold",
                        "ComparisonOperator",
                        "TreatMissingData",
                        "EvaluateLowSampleCountPercentile",
                        "Metrics",
                        "Tags",
                        "ThresholdMetricId",
                    }
                    filtered_alarm = {k: v for k, v in alarm.items() if k in valid_keys}
                    cloudwatch_client.put_metric_alarm(**filtered_alarm)
                    # now it should contain the SNS topic
                    topics = [sns_topic]
                except Exception:
                    self.logger.exception(
                        "Error adding SNS action to alarm %s", alarm.get("AlarmName")
                    )
                    continue
                self.logger.info(
                    "SNS action added to alarm %s!", alarm.get("AlarmName")
                )
            else:
                self.logger.warning(
                    "Cannot hook alarm without SNS topic and SNS topic is not supplied, skipping..."
                )
            for topic in topics:
                if topic in subscribed_topics:
                    self.logger.info(
                        "Already subscribed to topic %s in this transaction, skipping...",
                        topic,
                    )
                    continue
                self.logger.info("Checking topic %s...", topic)
                subscriptions = sns_client.list_subscriptions_by_topic(
                    TopicArn=topic
                ).get("Subscriptions", [])
                hostname = urlparse(keep_api_url).hostname
                already_subscribed = any(
                    hostname in sub["Endpoint"]
                    and not sub["SubscriptionArn"] == "PendingConfirmation"
                    for sub in subscriptions
                )
                if not already_subscribed:
                    url_with_api_key = keep_api_url.replace(
                        "https://", f"https://api_key:{api_key}@"
                    )
                    self.logger.info("Subscribing to topic %s...", topic)
                    sns_client.subscribe(
                        TopicArn=topic,
                        Protocol="https",
                        Endpoint=url_with_api_key,
                    )
                    self.logger.info("Subscribed to topic %s!", topic)
                    subscribed_topics.append(topic)
                    # we need to subscribe to only one SNS topic per alarm, o/w we will get many duplicates
                    break
                else:
                    self.logger.info(
                        "Already subscribed to topic %s, skipping...", topic
                    )
        self.logger.info("Webhook setup completed!")

    @staticmethod
    def format_alert(event: dict) -> AlertDto:
        logger = logging.getLogger(__name__)
        # if its confirmation event, we need to confirm the subscription
        if event.get("Type") == "SubscriptionConfirmation":
            # TODO - do we want to keep it in the db somehow?
            #        do we want to validate that the tenant id exist?
            logger.info("Confirming subscription...")
            subscribe_url = event.get("SubscribeURL")
            resp = requests.get(subscribe_url)
            logger.info("Subscription confirmed!")
            # Done
            return
        # else, we need to parse the event and create an alert
        try:
            alert = json.loads(event.get("Message"))
        except Exception:
            logger.exception("Error parsing cloudwatch alert", extra={"event": event})
            return
        return AlertDto(
            # there is no unique id in the alarm so let's hash the alarm
            id=hashlib.sha256(event.get("Message").encode()).hexdigest(),
            name=alert.get("AlarmName"),
            status=alert.get("NewStateValue"),
            severity=None,  # AWS Cloudwatch doesn't have severity
            lastReceived=str(
                datetime.datetime.fromisoformat(alert.get("StateChangeTime"))
            ),
            fatigueMeter=random.randint(0, 100),
            description=alert.get("AlarmDescription"),
            source=["cloudwatch"],
            **alert,
        )


class CloudwatchLogsProvider(CloudwatchProvider):
    """
    CloudwatchLogsProvider is a class that provides a way to read data from AWS Cloudwatch Logs.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        self.aws_client_type = "logs"

    def _query(self, **kwargs: dict) -> dict:
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
        super().__init__(provider_id, config)
        self.aws_client_type = "cloudwatch"

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
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    cloudwatch_provider = CloudwatchMetricsProvider(
        context_manager, "cloudwatch-prod", config
    )
    results = cloudwatch_provider.query(
        query="fields @timestamp, @message, @logStream, @log | sort @timestamp desc | limit 20",
        log_group="Test",
    )
    print(results)
