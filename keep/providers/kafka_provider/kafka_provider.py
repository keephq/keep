"""
Kafka Provider is a class that allows to ingest/digest data from Grafana.
"""

import dataclasses
import inspect
import logging

import pydantic

# from confluent_kafka import Consumer, KafkaError, KafkaException
from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable

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
        default=None,
        metadata={
            "required": False,
            "description": "Username",
            "hint": "Kafka username (Optional for SASL authentication)",
            "sensitive": True,
        },
    )
    password: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Password",
            "hint": "Kafka password (Optional for SASL authentication)",
            "sensitive": True,
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
                if isinstance(var_value, KafkaProvider):
                    client_id = var_value.context_manager.tenant_id
                    provider_id = var_value.provider_id
                    break
            if client_id:
                return client_id, provider_id
            frame = frame.f_back
        return None, None


class KafkaProvider(BaseProvider):
    """
    Kafka provider class.
    """

    PROVIDER_CATEGORY = ["Developer Tools", "Queues"]

    PROVIDER_DISPLAY_NAME = "Kafka"
    PROVIDER_SCOPES = [
        ProviderScope(
            name="topic_read",
            description="The kafka user that have permissions to read the topic.",
            mandatory=True,
            alias="Topic Read",
        )
    ]
    PROVIDER_TAGS = ["queue"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False
        self.consumer = None
        self.err = ""
        # patch all Kafka loggers to contain the tenant_id
        for logger_name in logging.Logger.manager.loggerDict:
            if logger_name.startswith("kafka"):
                logger = logging.getLogger(logger_name)
                if not any(isinstance(f, ClientIdInjector) for f in logger.filters):
                    self.logger.info(f"Patching kafka logger {logger_name}")
                    logger.addFilter(ClientIdInjector())

    def validate_scopes(self):
        scopes = {"topic_read": False}
        self.logger.info("Validating kafka scopes")
        conf = self._get_conf()

        try:
            self.logger.info("Trying to connect to Kafka with SASL_SSL")
            consumer = KafkaConsumer(self.authentication_config.topic, **conf)
        except NoBrokersAvailable:
            # retry with SASL_PLAINTEXT
            try:
                conf["security_protocol"] = "SASL_PLAINTEXT"
                self.logger.info("Trying to connect to Kafka with SASL_PLAINTEXT")
                consumer = KafkaConsumer(self.authentication_config.topic, **conf)
            except NoBrokersAvailable:
                self.err = f"Auth/Network problem: could not connect to Kafka at {self.authentication_config.host}"
                self.logger.warning(self.err)
                scopes["topic_read"] = self.err
                return scopes
        except KafkaError as e:
            self.err = str(e)
            self.logger.warning(f"Error connecting to Kafka: {e}")
            scopes["topic_read"] = self.err or "Could not connect to Kafka "
            return scopes

        topics = consumer.topics()
        if self.authentication_config.topic in topics:
            self.logger.info(f"Topic {self.authentication_config.topic} exists")
            scopes["topic_read"] = True
            return scopes
        else:
            self.err = f"The user have permission to Kafka, but topic '{self.authentication_config.topic}' does not exist or the user does not have permissions to read it - available topics: {consumer.topics()}"
            self.logger.warning(self.err)
            scopes["topic_read"] = self.err
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
                    "security_protocol": (
                        "SASL_SSL"
                        if self.authentication_config.username
                        else "PLAINTEXT"
                    ),
                    "sasl_mechanism": "PLAIN",
                    "sasl_plain_username": self.authentication_config.username,
                    "sasl_plain_password": self.authentication_config.password,
                }
            )
        return basic_conf

    def status(self):
        """
        Get the status of the provider.

        Returns:
            dict: The status of the provider.
        """
        if not self.consumer:
            status = "not-initialized"
        else:
            try:
                status = {
                    str(conn_id): conn.state
                    for conn_id, conn in self.consumer._client._conns.items()
                }
            except Exception as e:
                status = str(e)

        return {
            "status": status,
            "error": self.err,
        }

    def start_consume(self):
        self.consume = True
        conf = self._get_conf()
        try:
            self.consumer = KafkaConsumer(self.authentication_config.topic, **conf)
        except NoBrokersAvailable:
            # retry with SASL_PLAINTEXT
            try:
                conf["security_protocol"] = "SASL_PLAINTEXT"
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
                        except Exception:
                            self.logger.warning("Error pushing alert to API")
                            pass
            except Exception:
                self.logger.exception("Error consuming message from Kafka")
                break

        # finally, dispose
        if self.consumer:
            try:
                self.consumer.close()
            except Exception:
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
