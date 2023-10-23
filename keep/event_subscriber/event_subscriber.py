import logging
from concurrent.futures import ThreadPoolExecutor

from keep.providers.base.base_provider import BaseProvider
from keep.providers.providers_factory import ProvidersFactory


class EventSubscriber:
    @staticmethod
    def get_instance() -> "EventSubscriber":
        if not hasattr(EventSubscriber, "_instance"):
            EventSubscriber._instance = EventSubscriber()
        return EventSubscriber._instance

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.consumers = []
        self.executor = ThreadPoolExecutor()

    def add_consumer(self, consumer_provider: BaseProvider):
        """Add a consumer (on installation)

        Args:
            consumer_provider (_type_): _description_
        """
        self.logger.info("Adding consumer %s", consumer_provider)
        # submit the consumer to the executor
        self.executor.submit(consumer_provider.start_consume)
        self.consumers.append(consumer_provider)
        self.logger.info(
            "Started consumer thread for event provider %s", consumer_provider
        )

    async def start(self):
        """Runs the event subscriber in server mode"""
        consumer_providers = ProvidersFactory.get_consumer_providers()
        for consumer_provider in consumer_providers:
            # get the consumer for the event provider
            self.logger.info(
                "Getting consumer for event provider %s", consumer_provider
            )
            # submit the consumer to the executor
            self.executor.submit(consumer_provider.start_consume)
            self.consumers.append(consumer_provider)
            self.logger.info(
                "Started consumer thread for event provider %s", consumer_provider
            )

    def remove_consumer(self, consumer_provider: BaseProvider):
        """Remove a consumer (on uninstallation)

        Args:
            consumer_provider (_type_): _description_
        """
        self.logger.info("Removing consumer %s", consumer_provider)
        for cp in self.consumers:
            if cp.provider_id == consumer_provider.provider_id:
                cp.stop_consume()
                break
        self.logger.info("Removed consumer %s", consumer_provider)

    def stop(self):
        """Stops the consumers"""
        for consumer in self.consumers:
            self.logger.info("Stopping consumer %s", consumer)
            consumer.stop_consume()
            self.logger.info("Stopped consumer %s", consumer)

        # Shutdown the executor
        self.logger.info("Shutting down the executor")
        self.executor.shutdown()
        self.logger.info("Executor shutdown complete")
