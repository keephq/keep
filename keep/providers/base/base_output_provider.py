"""
Base class for output providers.
"""
import abc

from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class BaseOutputProvider(BaseProvider, metaclass=abc.ABCMeta):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.logger.info(
            "Provider initialized",
            extra={"provider": self.__class__.__name__},
        )

    @abc.abstractmethod
    def output(self, alert_message: str, **context: dict):
        """
        Output alert message.

        Args:
            alert_message (str): The alert message to output.
            **context (dict): Additional context used to enrich the alert message.
        """
        raise NotImplementedError("output() method not implemented")
