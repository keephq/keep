"""
Base class for all providers.
"""
import abc
import logging

from keep.providers.models.provider_config import ProviderConfig


class BaseProvider(metaclass=abc.ABCMeta):
    def __init__(self, config: ProviderConfig):
        """
        Initialize a provider.

        Args:
            **kwargs: Provider configuration loaded from the provider yaml file.
        """
        # Initalize logger for every provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = config
        self.validate_config()
        self.logger.debug(
            "Initializing provider", extra={"provider": self.__class__.__name__}
        )

    @abc.abstractmethod
    def validate_config():
        """
        Validate provider configuration.
        """
        raise NotImplementedError("validate_config() method not implemented")

    def notify(self, alert_message: str, **kwargs: dict):
        """
        Output alert message.

        Args:
            alert_message (str): The alert message to output.
            **context (dict): Additional context used to enrich the alert message.
        """
        raise NotImplementedError("notify() method not implemented")

    def query(self, query: str, **kwargs: dict):
        """
        Query the provider using the given query

        Args:
            query (str): _description_

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("query() method not implemented")
