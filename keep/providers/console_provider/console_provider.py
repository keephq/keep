"""
Simple Console Output Provider
"""
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


class ConsoleProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    def validate_config():
        # No configuration to validate, so just do nothing.
        # For example, this could be the place where you validate that the expected keys are present in the configuration.
        # e.g. if "pagerduty_api_key" is not present in self.config.authentication
        pass

    def notify(self, alert_message: str, **kwargs: dict):
        """
        Output alert message simply using the print method.

        Args:
            alert_message (str): The alert message to be printed in to the console
        """
        self.logger.debug("Outputting alert message to console")
        print(alert_message.format(**kwargs))
        self.logger.debug("Alert message outputted to console")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    # Initalize the provider and provider config
    config = {
        "id": "console",
        "provider_type": "console",
        "description": "Console Output Provider",
        "authentication": {},
    }
    provider = ProvidersFactory.get_provider(config)
    provider.notify("Simple alert showing context with name: {name}", name="John Doe")
