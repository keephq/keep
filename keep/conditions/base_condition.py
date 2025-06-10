"""
Base class for all conditions.
"""
import abc
import logging

from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import MustacheIOHandler


class BaseCondition(metaclass=abc.ABCMeta):
    def __init__(
        self,
        context_manager: ContextManager,
        condition_type,
        condition_name,
        condition_config,
        **kwargs
    ):
        """
        Initialize a provider.

        Args:
            **kwargs: Provider configuration loaded from the provider yaml file.
        """
        # Initalize logger for every provider
        self.logger = logging.getLogger(self.__class__.__name__)
        self.condition_type = condition_type
        self.condition_config = condition_config
        self.condition_name = condition_name
        self.io_handler = MustacheIOHandler(context_manager)
        self.context_manager = context_manager
        self.condition_context = {}
        self.condition_alias = condition_config.get("alias") or condition_name
        self.logger.debug(
            "Initializing condition", extra={"condition": self.__class__.__name__}
        )

    @abc.abstractmethod
    def apply(self, **kwargs) -> bool:
        """
        Validate provider configuration.
        """
        raise NotImplementedError("apply() method not implemented")

    def get_compare_to(self):
        """Get the comparison baseline.
           For example, for threshold conditions it'll be the threshold.

        Args:
            step_output (_type_): _description_

        Returns:
            _type_: _description_
        """
        compare_to = self.condition_config.get("compare_to")
        compare_to = self.io_handler.render(compare_to)
        return compare_to

    def get_compare_value(self):
        """Get the value to compare. The actual value from the step output.

        Args:
            step_output (_type_): _description_

        Returns:
            _type_: _description_
        """
        compare_value = self.condition_config.get("value")
        compare_value = self.io_handler.render(compare_value).strip()
        return compare_value
