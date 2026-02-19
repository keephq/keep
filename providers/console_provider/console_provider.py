"""
Simple Console Output Provider
"""

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


class ConsoleProvider(BaseProvider):
    """Send alerts data to the console (debugging purposes)."""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        # No configuration to validate, so just do nothing.
        # For example, this could be the place where you validate that the expected keys are present in the configuration.
        # e.g. if "pagerduty_api_key" is not present in self.config.authentication
        pass

    def dispose(self):
        # No need to dispose of anything, so just do nothing.
        pass

    def _query(
        self,
        message: str = "",
        logger: bool = False,
        severity: str = "info",
        **kwargs,  # TODO: remove '**kwargs', when we will pop it from the notify method in the base provider
    ):
        return self._notify(message, logger, severity)

    def _notify(
        self,
        message: str = "",
        logger: bool = False,
        severity: str = "info",
        **kwargs,
        # TODO: remove '**kwargs', when we will pop it from the notify method in the base provider
    ):
        """
        Output alert message simply using the print method.

        Args:
            message (str): The message to be printed in to the console
            logger (bool): Whether to use the logger or not
            severity (str): The severity of the message if logger is True
        """
        self.logger.debug("Outputting alert message to console")
        if logger:
            try:
                getattr(self.logger, severity)(message)
            except AttributeError:
                self.logger.error(f"Invalid log level {severity}")
                # default to print
                print(message)
        # use print
        else:
            print(message)
        self.logger.debug("Alert message outputted to console")
        return message


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Initalize the provider and provider config
    config = {
        "description": "Console Output Provider",
        "authentication": {},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="mock",
        provider_type="console",
        provider_config=config,
    )
    provider.notify(
        alert_message="Simple alert showing context with name: John Doe",
        logger=True,
        severity="critical",
    )
