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
        self.logger.debug(
            "Initializing provider", extra={"provider": self.__class__.__name__}
        )

    @abc.abstractmethod
    def validate_config():
        """
        Validate provider configuration.
        """
        raise NotImplementedError("validate_config() method not implemented")
