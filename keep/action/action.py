import re

import chevron
import click
import requests

from keep.exceptions.action_error import ActionError
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider


class Action:
    def __init__(self, name: str, provider: BaseProvider, provider_context: dict):
        self.name = name
        self.provider = provider
        self.provider_context = provider_context
        self.io_handler = IOHandler()

        # Whether Keep should shorten urls in the message or not
        self.shorten_urls = False
        self.click_context = click.get_current_context(silent=True)
        if (
            self.click_context
            and "api_key" in self.click_context.params
            and "api_url" in self.click_context.params
        ):
            self.shorten_urls = True

    def run(self, alert_context):
        try:
            self._render_context(self.provider_context, alert_context)
            self.provider.notify(**self.provider_context)
        except Exception as e:
            raise ActionError(e)

    def _render_context(self, context_to_render: dict, alert_context: dict):
        """
        Iterates the provider context and renders it using the alert context.
        """
        for key, value in context_to_render.items():
            if isinstance(value, str):
                context_to_render[key] = self._render_template_with_context(
                    value, alert_context
                )
            elif isinstance(value, list):
                self._render_list_context(value, alert_context)
            elif isinstance(value, dict):
                self._render_context(value, alert_context)

    def _render_list_context(self, context_to_render: list, alert_context: dict):
        """
        Iterates the provider context and renders it using the alert context.
        """
        for i in range(0, len(context_to_render)):
            value = context_to_render[i]
            if isinstance(value, str):
                context_to_render[i] = self._render_template_with_context(
                    value, alert_context
                )
            if isinstance(value, list):
                self._render_list_context(value, alert_context)
            if isinstance(value, dict):
                self._render_context(value, alert_context)

    def _render_template_with_context(self, template: str, alert_context: dict) -> str:
        """
        Renders a template with the given context.

        Args:
            template (str): template (string) to render
            alert_context (dict): alert run context

        Returns:
            str: rendered template
        """
        rendered_template = chevron.render(template, alert_context)

        # shorten urls if enabled
        if self.shorten_urls:
            rendered_template = self.__patch_urls(rendered_template)

        return rendered_template

    def __get_short_urls(self, urls: list) -> dict:
        """
        Shorten URLs using Keep API.

        Args:
            urls (list): list of urls to shorten
            api_url (str): the keep api url
            api_key (str): the keep api key

        Returns:
            dict: a dictionary containing the original url as key and the shortened url as value
        """
        try:
            api_url = self.click_context.params.get("api_url")
            api_key = self.click_context.params.get("api_key")
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

    def __patch_urls(self, rendered_template: str) -> str:
        """
        shorten URLs found in the message.

        Args:
            rendered_template (str): The rendered template that might contain URLs
        """
        urls = re.findall(
            "https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+/?.*", rendered_template
        )
        # didn't find any url
        if not urls:
            return rendered_template

        shortened_urls = self.__get_short_urls(urls)
        for url, shortened_url in shortened_urls.items():
            rendered_template = rendered_template.replace(url, shortened_url)
        return rendered_template
