"""
Kafka Provider is a class that allows to ingest/digest data from Grafana.
"""
import dataclasses

import pydantic
from confluent_kafka import Consumer, KafkaError, KafkaException

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

    def validate_scopes(self):
        scopes = {"topic_read": False}
        self.err = ""
        self.logger.info("Validating kafka scopes")
        conf = self._get_conf()

        def validate_read_topic(err):
            self.logger.info("Validating kafka topic read scope")
            self.err += str(err)

        conf["error_cb"] = validate_read_topic

        consumer = Consumer(conf)
        try:
            # try subscribe and see what happens
            consumer.subscribe([self.authentication_config.topic])
            event = consumer.poll(3.0)
            if event and event.error():
                self.err += str(event.error())
        except KafkaException as e:
            self.logger.warning(f"No scopes: {e}")
            scopes["topic_read"] = self.err or f"Could not authenticate to Kafka"
            return scopes
        except Exception as e:
            self.logger.warning(f"Unknown error while connecting to Kafka")
            scopes["topic_read"] = self.err or str(e)
            return scopes

        # specific problems we already know
        if "Connection refused" in self.err:
            scopes[
                "topic_read"
            ] = f"Connection refused: could not connect to Kafka at {self.authentication_config.host}"
            return scopes
        elif "Authentication failed" in self.err:
            scopes[
                "topic_read"
            ] = f"Authentication failed: could not authenticate to Kafka at {self.authentication_config.host}"
            return scopes
        elif "Unknown topic" in self.err:
            scopes[
                "topic_read"
            ] = f"Unknown topic: could not find topic {self.authentication_config.topic} at {self.authentication_config.host}"
            return scopes

        # generic problem we don't know about yet:
        if self.err:
            scopes["topic_read"] = self.err
        else:
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

    def _error_callback(self, err):
        self.logger.error("Error: {}".format(err))
        # if the authentication fails, raise an exception
        if err.code() == KafkaError._AUTHENTICATION:
            raise Exception("Authentication error: {}".format(err))
        # if the topic does not exist, raise an exception
        elif err.code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
            raise Exception("Topic {} does not exist".format(err))
        elif err.code() == KafkaError._MAX_POLL_EXCEEDED:
            self.logger.warning("Max poll exceeded, reconsuming")
            conf = self._get_conf()
            self.consumer = Consumer(conf)
            self.consumer.subscribe([self.authentication_config.topic])
            # the consumer will be reconsumed in  the mainloop
            self.logger.info("Reconsumed")
        else:
            self.logger.warning(f"Unknown error, stopping to listen: {err}")
            self.consumer.close()

    def _get_conf(self):
        basic_conf = {
            "bootstrap.servers": self.authentication_config.host,
            "group.id": "keephq-group",
            "error_cb": self._error_callback,
            "auto.offset.reset": "earliest",
            "debug": "all",
        }

        if self.authentication_config.username and self.authentication_config.password:
            basic_conf.update(
                {
                    "security.protocol": "SASL_PLAINTEXT",
                    "sasl.mechanisms": "PLAIN",
                    "sasl.username": self.authentication_config.username,
                    "sasl.password": self.authentication_config.password,
                }
            )
        return basic_conf

    def start_consume(self):
        """
        Get the Kafka consumer.

        Returns:
            kafka.KafkaConsumer: Kafka consumer
        """
        self.consume = True
        conf = self._get_conf()
        self.consumer = Consumer(conf)
        self.consumer.subscribe([self.authentication_config.topic])
        while self.consume:
            event = self.consumer.poll(1.0)
            if event:
                if event.error():
                    self.logger.error("Error: {}".format(event.error()))
                    self._error_callback(event.error())
                if event:
                    self.logger.info("Got event: {}".format(event.value()))
                    # now push it via the alerts API
                    # note that in the future pulling from topics will probably will be in another service
                    self._push_alert(event.value())
            else:
                self.logger.debug("No message in the queue")
        self.logger.info("Consuming stopped")

    def stop_consume(self):
        self.consume = False
        # dispose
        if self.consumer:
            try:
                self.consumer.close()
            except Exception as e:
                self.logger.exception("Error closing Kafka connection")
            self.consumer = None


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    # Before the provider can be run, we need to docker-compose up the kafka container
    # check the docker-compose in this folder
    # Now start the container
    host = "localhost:9092"
    topic = "alert"
    username = "admin"
    password = "admin-secret"

    context_manager = ContextManager(
        tenant_id="singletenant",
    )
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
    consumer = provider.get_consumer()
    consumer.start()
    print(alerts)
