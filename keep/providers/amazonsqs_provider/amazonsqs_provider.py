"""
Amazonsqs Provider is a class that allows to receive alerts and notify the Amazon SQS Queue
"""

import dataclasses
import inspect
import logging
import time
import uuid
from datetime import datetime

import boto3
import botocore
import pydantic

from keep.api.models.alert import AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class AmazonsqsProviderAuthConfig:
    """
    AmazonSQS authentication configuration.
    """

    access_key_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Access Key Id",
            "hint": "Access Key ID",
        },
    )
    secret_access_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Secret access key",
            "hint": "Secret access key",
            "sensitive": True,
        },
    )
    region_name: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Region name",
            "hint": "Region name: eg. us-east-1 | ap-sout-1 | etc.",
            "sensitive": False,
        },
    )
    sqs_queue_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "SQS Queue URL",
            "hint": "Example: https://sqs.ap-south-1.amazonaws.com/614100018813/Q2",
        },
    )


class ClientIdInjector(logging.Filter):
    def filter(self, record):
        # For this example, let's pretend we can obtain the client_id
        # by inspecting the caller or some context. Replace the next line
        # with the actual logic to get the client_id.
        client_id, provider_id = self.get_client_id_from_caller()
        if not hasattr(record, "extra"):
            record.extra = {
                "client_id": client_id,
                "provider_id": provider_id,
            }
        return True

    def get_client_id_from_caller(self):
        # Here, you should implement the logic to extract client_id based on the caller.
        # This can be tricky and might require you to traverse the call stack.
        # Return a default or None if you can't find it.
        import copy

        frame = inspect.currentframe()
        client_id = None
        while frame:
            local_vars = copy.copy(frame.f_locals)
            for var_name, var_value in local_vars.items():
                if isinstance(var_value, AmazonsqsProvider):
                    client_id = var_value.context_manager.tenant_id
                    provider_id = var_value.provider_id
                    break
            if client_id:
                return client_id, provider_id
            frame = frame.f_back
        return None, None


class AmazonsqsProvider(BaseProvider):
    """Sends and receive alerts from AmazonSQS."""

    PROVIDER_CATEGORY = ["Monitoring", "Queues"]
    PROVIDER_TAGS = ["queue"]

    alert_severity_dict = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    PROVIDER_DISPLAY_NAME = "AmazonSQS"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="Key-Id pair is valid and working",
            mandatory=True,
            alias="Authenticated",
        ),
        ProviderScope(
            name="sqs::read",
            description="Required privileges to receive alert from SQS",
            mandatory=True,
            alias="Read Access",
        ),
        ProviderScope(
            name="sqs::write",
            description="Required privileges to push messages to SQS",
            mandatory=False,
            alias="Write Access",
        ),
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self.consumer = None
        self.err = ""
        # patch all AmazonSQS loggers to contain the tenant_id
        for logger_name in logging.Logger.manager.loggerDict:
            if logger_name.startswith("amazonsqs"):
                logger = logging.getLogger(logger_name)
                if not any(isinstance(f, ClientIdInjector) for f in logger.filters):
                    self.logger.info(f"Patching amazonsqs logger {logger_name}")
                    logger.addFilter(ClientIdInjector())

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Amazonsqs provider.
        """
        self.logger.debug("Validating configuration for Amazonsqs provider")
        self.authentication_config = AmazonsqsProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def __get_sqs_client(self):
        if self.consumer is None:
            self.consumer = boto3.client(
                "sqs",
                region_name=self.authentication_config.region_name,
                aws_access_key_id=self.authentication_config.access_key_id,
                aws_secret_access_key=self.authentication_config.secret_access_key,
            )
        return self.consumer

    def validate_scopes(self) -> dict[str, bool | str]:
        self.logger.info("Validating user scopes for AmazonSQS provider")
        scopes = {
            "authenticated": False,
            "sqs::read": False,
            "sqs::write": False,
        }
        sts = boto3.client(
            "sts",
            region_name=self.authentication_config.region_name,
            aws_access_key_id=self.authentication_config.access_key_id,
            aws_secret_access_key=self.authentication_config.secret_access_key,
        )
        try:
            sts.get_caller_identity()
            self.logger.info(
                "User identity fetched successfully, user is authenticated."
            )
            scopes["authenticated"] = True
        except botocore.exceptions.ClientError as e:
            self.logger.error(
                "Error while getting user identity, authentication failed",
                extra={"exception": str(e)},
            )
            scopes["authenticated"] = str(e)
            return scopes

        try:
            self.__write_to_queue(
                message="KEEP_SCOPE_TEST_MSG_PLEASE_IGNORE",
                dedup_id=str(uuid.uuid4()),
                group_id="keep",
            )
            self.logger.info("All scopes verified successfully")
            scopes["sqs::write"] = True
            scopes["sqs::read"] = True
        except botocore.exceptions.ClientError as e:
            self.logger.error(
                "User does not have permission to write to SQS queue",
                extra={"exception": str(e)},
            )
            scopes["sqs::write"] = str(e)
            try:
                self.__read_from_queue()
                self.logger.info("User has permission to read from SQS Queue")
                scopes["sqs::read"] = True
            except botocore.exceptions.ClientError as e:
                self.logger.error(
                    "User does not have permission to read from SQS queue",
                    extra={"exception": str(e)},
                )
                scopes["sqs::read"] = str(e)
        return scopes

    def __read_from_queue(self):
        self.logger.info("Getting messages from SQS Queue")
        try:
            return self.__get_sqs_client.receive_message(
                QueueUrl=self.authentication_config.sqs_queue_url,
                MessageAttributeNames=["All"],
                MessageSystemAttributeNames=["All"],
                MaxNumberOfMessages=10,
                WaitTimeSeconds=10,
            )
        except Exception as e:
            self.logger.error(
                "Error while reading from SQS Queue", extra={"exception": str(e)}
            )

    def __write_to_queue(self, message, group_id, dedup_id, **kwargs):
        try:
            self.logger.info("Sending message to SQS Queue")
            message = str(message)
            group_id = str(group_id)
            dedup_id = str(dedup_id)
            is_fifo = self.authentication_config.sqs_queue_url.endswith(".fifo")
            self.logger.info("Building MessageAttributes")
            msg_attrs = {
                key: {"StringValue": kwargs[key], "DataType": "String"}
                for key in kwargs
            }
            if is_fifo:
                if not dedup_id or not group_id:
                    self.logger.error(
                        "Mandatory to provide dedup_id (Message deduplication ID) & group_id (Message group ID) when pushing to fifo queue"
                    )
                    raise Exception(
                        "Mandatory to provide dedup_id (Message deduplication ID) & group_id (Message group ID) when pushing to fifo queue"
                    )
                response = self.__get_sqs_client.send_message(
                    QueueUrl=self.authentication_config.sqs_queue_url,
                    MessageAttributes=msg_attrs,
                    MessageBody=message,
                    MessageDeduplicationId=dedup_id,
                    MessageGroupId=group_id,
                )
            else:
                response = self.__get_sqs_client.send_message(
                    QueueUrl=self.authentication_config.sqs_queue_url,
                    MessageAttributes=msg_attrs,
                    MessageBody=message,
                )

            self.logger.info(
                "Successfully pushed the message to SQS",
                extra={"response": str(response)},
            )
            return response
        except Exception as e:
            self.logger.error(
                "Error while writing to SQS queue", extra={"exception": str(e)}
            )
            raise e

    def __delete_from_queue(self, receipt: str):
        self.logger.info("Deleting message from SQS Queue")
        try:
            self.__get_sqs_client.delete_message(
                QueueUrl=self.authentication_config.sqs_queue_url, ReceiptHandle=receipt
            )
            self.logger.info("Successfully deleted message from SQS Queue")
        except Exception as e:
            self.logger.error(
                "Error while deleting message from SQS queue",
                extra={"exception": str(e)},
            )
            raise e

    @staticmethod
    def get_status_or_default(status_value):
        try:
            # Check if status_value is a valid member of AlertStatus
            return AlertStatus(status_value)
        except ValueError:
            # If not, return the default AlertStatus.FIRING
            return AlertStatus.FIRING

    def _notify(self, message, group_id, dedup_id, **kwargs):
        return self.__write_to_queue(
            message=message, group_id=group_id, dedup_id=dedup_id, **kwargs
        )

    def start_consume(self):
        self.consume = True
        while self.consume:
            response = self.__read_from_queue()
            messages = response.get("Messages", [])
            if not messages:
                self.logger.info("No messages found. Queue is empty!")

            for message in messages:
                try:
                    labels = {}
                    attrs = message.get("MessageAttributes", {})
                    for msg_attr in attrs:
                        labels[msg_attr.lower()] = attrs[msg_attr].get(
                            "StringValue", attrs[msg_attr].get("BinaryValue", "")
                        )

                    alert_dict = {
                        "id": message["MessageId"],
                        "name": labels.get("name", message["Body"]),
                        "description": labels.get("description", message["Body"]),
                        "message": message["Body"],
                        "status": AmazonsqsProvider.get_status_or_default(
                            labels.get("status", "firing")
                        ),
                        "severity": self.alert_severity_dict.get(
                            labels.get("severity", "high"), AlertSeverity.HIGH
                        ),
                        "lastReceived": datetime.fromtimestamp(
                            float(message["Attributes"]["SentTimestamp"]) / 1000
                        ).isoformat(),
                        "firingStartTime": datetime.fromtimestamp(
                            float(message["Attributes"]["SentTimestamp"]) / 1000
                        ).isoformat(),
                        "labels": labels,
                        "source": ["amazonsqs"],
                    }
                    self._push_alert(alert_dict)
                    self.__delete_from_queue(receipt=message["ReceiptHandle"])
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")

            time.sleep(0.1)
        self.logger.info("Consuming stopped")

    def stop_consume(self):
        self.consume = False
