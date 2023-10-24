"""
Kafka Provider is a class that allows to ingest/digest data from Grafana.
"""
import dataclasses
import logging

import pydantic

# from confluent_kafka import Consumer, KafkaError, KafkaException
from kafka import KafkaConsumer
from kafka.errors import (
    KafkaError,
    KafkaTimeoutError,
    NoBrokersAvailable,
    TopicAuthorizationFailedError,
)

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class KafkaProviderAuthConfig:
    """
    Kafka authentication configuration.
    """

    host: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Kafka host",
            "hint": "e.g. https://kafka:9092",
        },
    )
    topic: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "The topic to subscribe to",
            "hint": "e.g. alerts-topic",
        },
    )
    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Username",
            "hint": "Kafka username (Optional for SASL authentication)",
        },
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Password",
            "hint": "Kafka password (Optional for SASL authentication)",
        },
    )


class ClientIdInjector(logging.Filter):
    def filter(self, record):
        # For this example, let's pretend we can obtain the client_id
        # by inspecting the caller or some context. Replace the next line
        # with the actual logic to get the client_id.
        client_id = self.get_client_id_from_caller()
        record.client_id = client_id
        return True

    def get_client_id_from_caller(self):
        # Here, you should implement the logic to extract client_id based on the caller.
        # This can be tricky and might require you to traverse the call stack.
        # Return a default or None if you can't find it.
        return "some-client-id"


class KafkaProvider(BaseProvider):
    """
    Kafka provider class.
    """

    PROVIDER_SCOPES = [
        ProviderScope(
            name="topic_read",
            description="The kafka user that have permissions to read the topic.",
            mandatory=True,
            documentation_url="https://docs.datadoghq.com/account_management/rbac/permissions/#monitors",
            alias="Topic Read",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self.consumer = None
        # patch all Kafka loggers to contain the tenant_id
        for logger_name in logging.Logger.manager.loggerDict:
            if logger_name.startswith("kafka"):
                logger = logging.getLogger(logger_name)
                if not any(isinstance(f, ClientIdInjector) for f in logger.filters):
                    logger.addFilter(ClientIdInjector())

    def validate_scopes(self):
        scopes = {"topic_read": False}
        self.err = ""
        self.logger.info("Validating kafka scopes")
        conf = self._get_conf()

        try:
            consumer = KafkaConsumer(self.authentication_config.topic, **conf)
        except NoBrokersAvailable:
            self.err = f"Auth/Network problem: could not connect to Kafka at {self.authentication_config.host}"
            self.logger.warning(self.err)
            scopes["topic_read"] = self.err
            return scopes
        except KafkaError as e:
            self.err = str(e)
            self.logger.warning(f"Error connecting to Kafka: {e}")
            scopes["topic_read"] = self.err or f"Could not connect to Kafka "
            return scopes

        scopes["topic_read"] = True
        return scopes

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Kafka provider.

        """
        self.authentication_config = KafkaProviderAuthConfig(
            **self.config.authentication
        )

    def _get_conf(self):
        basic_conf = {
            "bootstrap_servers": self.authentication_config.host,
            "group_id": "keephq-group",
            "auto_offset_reset": "earliest",
            "enable_auto_commit": True,  # this is typically needed
            "reconnect_backoff_max_ms": 30000,  # 30 seconds
            "client_id": self.context_manager.tenant_id,  # add tenant id to the logs
        }

        if self.authentication_config.username and self.authentication_config.password:
            basic_conf.update(
                {
                    "security_protocol": "SASL_PLAINTEXT",
                    "sasl_mechanism": "PLAIN",
                    "sasl_plain_username": self.authentication_config.username,
                    "sasl_plain_password": self.authentication_config.password,
                }
            )
        return basic_conf

    def start_consume(self):
        self.consume = True
        conf = self._get_conf()
        try:
            self.consumer = KafkaConsumer(self.authentication_config.topic, **conf)
        except NoBrokersAvailable:
            self.logger.exception(
                f"Could not connect to Kafka at {self.authentication_config.host}"
            )
            return

        while self.consume:
            try:
                topics = self.consumer.poll(timeout_ms=1000)
                if not topics:
                    continue

                for tp, records in topics.items():
                    for record in records:
                        self.logger.info(
                            f"Received message {record.value} from topic {tp.topic} partition {tp.partition}"
                        )
                        try:
                            self._push_alert(record.value)
                        except Exception as e:
                            self.logger.warning("Error pushing alert to API")
                            pass
            except Exception as e:
                self.logger.exception("Error consuming message from Kafka")
                break

        # finally, dispose
        if self.consumer:
            try:
                self.consumer.close()
            except Exception as e:
                self.logger.exception("Error closing Kafka connection")
            self.consumer = None
        self.logger.info("Consuming stopped")

    def stop_consume(self):
        self.consume = False


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    os.environ["KEEP_API_URL"] = "http://localhost:8080"
    # Before the provider can be run, we need to docker-compose up the kafka container
    # check the docker-compose in this folder
    # Now start the container
    host = "localhost:9092"
    topic = "alert"
    username = "admin"
    password = "admin-secret"
    from keep.api.core.dependencies import SINGLE_TENANT_UUID

    context_manager = ContextManager(tenant_id=SINGLE_TENANT_UUID)
    config = {
        "authentication": {
            "host": host,
            "topic": topic,
            "username": username,
            "password": password,
        }
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="kafka-keephq",
        provider_type="kafka",
        provider_config=config,
    )
    provider.start_consume()
