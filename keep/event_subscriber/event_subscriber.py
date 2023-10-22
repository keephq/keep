import logging

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
        self.consumer_threads = []

    async def start(self):
        """Runs the event subscriber in server mode"""
        consumer_providers = ProvidersFactory.get_consumer_providers()
        for consumer_provider in event_providers:
            # get the consumer for the event provider
            self.logger.info(
                "Getting consumer for event provider %s", consumer_provider
            )
            # start the consumer in a separate thread
            thread = threading.Thread(
                target=consumer_provider.start_consume,
                name=f"consumer-{consumer_provider}",
            )
            thread.start()
            self.consumers.append(consumer_provider)
            self.consumer_threads.append(thread)  # Append thread to the list
            self.logger.info(
                "Started consumer thread for event provider %s", consumer_provider
            )

    def stop(self):
        """Stops the consumers"""
        for consumer in self.consumers:
            self.logger.info("Stopping consumer %s", consumer)
            consumer.stop_consume()
            self.logger.info("Stopped consumer %s", consumer)

        # Join the threads
        self.logger.info("Joining consumer threads")
        for thread in self.consumer_threads:
            thread.join()
        self.logger.info("Joined consumer threads")
