"""
SlackOutput is a class that implements the BaseOutputProvider interface for Slack messages.
"""
from keep.exceptions.provider_config_exception import ProviderConfigException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class SlackProvider(BaseProvider):
    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    def validate_config(self):
        if not self.config.authentication.get("webhook-url"):
            raise ProviderConfigException(
                "SlackOutput requires a webhook-url in the authentication section of the configuration"
            )

    def notify(self, alert_message: str, **context: dict):
        """
        Output alert message to Slack using the Slack Incoming Webhook API
        https://api.slack.com/messaging/webhooks

        Args:
            alert_message (str): The alert message to send to Slack
        """
        self.logger.debug("Outputting alert message to Slack")
        import requests

        webhook_url = self.config.authentication.get("webhook-url")
        if webhook_url:
            requests.post(
                webhook_url,
                json={"text": alert_message.format(**context)},
            )
        else:
            self.logger.error(
                "SlackOutput requires a webhook-url in the authentication section of the configuration"
            )
        self.logger.debug("Alert message outputted to Slack")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    # Initalize the provider and provider config
    config = ProviderConfig(
        id="slack-test",
        provider_type="slack",
        description="Slack Output Provider",
        authentication={"webhook-url": slack_webhook_url},
    )
    provider = SlackProvider(config=config)
    provider.notify("Simple alert showing context with name: {name}", name="John Doe")
