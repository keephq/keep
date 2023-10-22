"""
Kafka Provider is a class that allows to ingest/digest data from Grafana.
"""
import dataclasses

import pydantic
from confluent_kafka import Consumer, KafkaError, KafkaException

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
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
            "hint": "Kafka username",
        },
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Password",
            "hint": "Kafka password",
        },
    )


class KafkaProvider(BaseProvider):
    """
    Kafka provider class.
    """

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.consume = False

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

    def start_consume(self):
        """
        Get the Kafka consumer.

        Returns:
            kafka.KafkaConsumer: Kafka consumer
        """
        self.consume = True
        conf = {
            "bootstrap.servers": self.authentication_config.host,
            "group.id": "keephq-group",
            "error_cb": self._error_callback,
            "auto.offset.reset": "earliest",
            "security.protocol": "SASL_PLAINTEXT",
            "sasl.mechanisms": "PLAIN",
            "sasl.username": self.authentication_config.username,
            "sasl.password": self.authentication_config.password,
        }

        consumer = Consumer(conf)
        consumer.subscribe([self.authentication_config.topic])
        while self.consume:
            event = consumer.poll(1.0)
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
