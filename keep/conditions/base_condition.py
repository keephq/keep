"""
Base class for all conditions.
"""
import abc
import logging


class BaseCondition(metaclass=abc.ABCMeta):
    def __init__(self, condition_type, condition_config, **kwargs):
        """
        Initialize a provider.

        Args:
            **kwargs: Provider configuration loaded from the provider yaml file.
        """
        # Initalize logger for every provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.condition_type = condition_type
        self.condition_config = condition_config
        self.logger.debug(
            "Initializing condition", extra={"condition": self.__class__.__name__}
        )

    @abc.abstractmethod
    def apply(self, context, step_output) -> bool:
        """
        Validate provider configuration.
        """
        raise NotImplementedError("apply() method not implemented")
