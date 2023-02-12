import logging
import re

import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider


class Action:
    def __init__(
        self, name: str, config, provider: BaseProvider, provider_context: dict
    ):
        self.name = name
        self.logger = logging.getLogger(__name__)
        self.provider = provider
        self.provider_context = provider_context
        self.action_config = config
        self.io_handler = IOHandler()
        self.context_manager = ContextManager.get_instance()

    def run(self):
        try:
            if self.action_config.get("foreach"):
                self._run_foreach()
            else:
                self._run_single()
        except Exception as e:
            raise ActionError(e)

    def _run_foreach(self):
        foreach_iterator = self.context_manager.get_actionable_results()
        for val in foreach_iterator:
            self.context_manager.set_for_each_context(
                val.get("condition").get("raw_value")
            )
            rendered_value = self.io_handler.render_context(self.provider_context)
            self.provider.notify(**rendered_value)

    def _run_single(self):
        self.io_handler.render_context(self.provider_context)
        self.provider.notify(**self.provider_context)

    def __get_short_urls(self, urls: list) -> dict:
        """
        Shorten URLs using Keep API.

        Args:
            urls (list): list of urls to shorten

        Returns:
            dict: a dictionary containing the original url as key and the shortened url as value
        """
        try:
            api_url = self.context_manager.click_context.params.get("api_url")
            api_key = self.context_manager.click_context.params.get("api_key")
            response = requests.post(
                f"{api_url}/s", json=urls, headers={"x-api-key": api_key}
            )
            if response.ok:
                return response.json()
            else:
                self.logger.error(
                    "Failed to request short URLs from API",
                    extra={
                        "response": response.text,
                        "status_code": response.status_code,
                    },
                )
        except Exception:
            self.logger.exception("Failed to request short URLs from API")
