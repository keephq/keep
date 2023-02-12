import logging
import os
import typing

import yaml

from keep.action.action import Action
from keep.alert.alert import Alert
from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.providers.providers_factory import ProvidersFactory
from keep.step.step import Step


class Parser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.context_manager = ContextManager.get_instance()
        self.io_handler = IOHandler()

    def parse(self, alert_file: str, providers_file: str = None) -> Alert:
        # Parse the alert YAML
        parsed_alert_yaml = self._parse_alerts_file_to_dict(alert_file)
        # Parse the providers (from the alert yaml or from the providers directory)
        self._parse_providers_config(parsed_alert_yaml, providers_file)
        # Parse the alert itself
        alert = self._parse_alert(parsed_alert_yaml.get("alert"))
        return alert

    def _parse_alerts_file_to_dict(self, alert_file: str) -> dict:
        self.logger.debug("Parsing alert")
        with open(alert_file, "r") as file:
            try:
                alert = yaml.safe_load(file)
            except yaml.YAMLError as e:
                self.logger.error(f"Error parsing {alert_file}: {e}")
                raise e
        return alert

    def _parse_alert(self, alert: dict) -> Alert:
        self.logger.debug("Parsing alert")
        alert_id = self._parse_id(alert)
        alert_owners = self._parse_owners(alert)
        alert_tags = self._parse_tags(alert)
        alert_steps = self._parse_steps(alert)
        alert_actions = self._parse_actions(alert)
        alert = Alert(
            alert_id=alert_id,
            alert_owners=alert_owners,
            alert_tags=alert_tags,
            alert_steps=alert_steps,
            alert_actions=alert_actions,
        )
        self.logger.debug("Alert parsed successfully")
        return alert

    def _parse_providers_config(
        self, alert: dict, providers_file: str
    ) -> typing.List[BaseProvider]:
        self.logger.debug("Parsing providers")
        if providers_file:
            self._parse_providers_from_file(providers_file)

        if alert.get("providers"):
            self._parse_providers_from_alert(alert)

    def _parse_providers_from_alert(self, alert: dict) -> typing.List[BaseProvider]:
        self.context_manager.providers_context.update(alert.get("providers"))
        self.logger.debug("Alert providers parsed successfully")

    def _parse_providers_from_file(
        self, providers_file: str
    ) -> typing.List[BaseProvider]:
        with open(providers_file, "r") as file:
            try:
                providers = yaml.safe_load(file)
            except yaml.YAMLError:
                self.logger.exception(f"Error parsing providers file {providers_file}")
                raise
            self.context_manager.providers_context.update(providers)
        self.logger.debug("Providers config parsed successfully")

    def _parse_id(self, alert) -> str:
        alert_id = alert.get("id")
        if alert_id is None:
            raise ValueError("Alert ID is required")
        return alert_id

    def _parse_owners(self, alert) -> typing.List[str]:
        alert_owners = alert.get("owners", [])
        return alert_owners

    def _parse_tags(self, alert) -> typing.List[str]:
        alert_tags = alert.get("tags", [])
        return alert_tags

    def _parse_steps(self, alert) -> typing.List[Step]:
        self.logger.debug("Parsing steps")
        alert_steps = alert.get("steps", [])
        alerts_steps_parsed = []
        for _step in alert_steps:
            provider = self._get_step_provider(_step)
            provider_parameters = _step.get("provider", {}).get("with")
            step_id = _step.get("name")
            step = Step(
                step_id=step_id,
                step_config=_step,
                provider=provider,
                provider_parameters=provider_parameters,
            )
            alerts_steps_parsed.append(step)
        self.logger.debug("Steps parsed successfully")
        return alerts_steps_parsed

    def _get_step_provider(self, _step: dict) -> dict:
        step_provider = _step.get("provider")
        step_provider_type = step_provider.pop("type")
        try:
            step_provider_config = step_provider.pop("config")
            provider_config = self._get_provider_config(step_provider_config)
            provider_id = self._get_provider_id(step_provider_config)
        # Support providers without config such as logfile or mock
        except KeyError:
            step_provider_config = {}
            provider_config = {"authentication": {}}
            provider_id = step_provider_type
        provider = ProvidersFactory.get_provider(
            provider_id, step_provider_type, provider_config
        )
        return provider

    def _parse_actions(self, alert) -> typing.List[Action]:
        self.logger.debug("Parsing actions")
        alert_actions = alert.get("actions", [])
        alert_actions_parsed = []
        for _action in alert_actions:
            name = _action.get("name")
            provider_config = _action.get("provider").get("config")
            provider_context = _action.get("provider").get("with")
            provider_id = self._get_provider_id(provider_config)
            provider_config = self._get_provider_config(provider_id)
            provider_type = provider_config.pop("type")
            provider = ProvidersFactory.get_provider(
                provider_id, provider_type, provider_config, **provider_context
            )
            action = Action(
                name=name,
                provider=provider,
                provider_context=provider_context,
            )
            alert_actions_parsed.append(action)
        self.logger.debug("Actions parsed successfully")
        return alert_actions_parsed

    def _get_provider_id(self, provider_type: str):
        """
        Translate {{ <provider_id>.<config_id> }} to a provider id

        Args:
            provider_type (str): _description_

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        provider_config = self.io_handler.render(provider_type)
        return provider_id

    def _get_provider_config(self, provider_id: str):
        """Get provider config according to provider_id

        Args:
            provider_type (_type_): _description_

        Raises:
            ValueError: _description_
        """
        provider_config = self.io_handler.render(provider_type)

        if not provider_config:
            raise ValueError(
                f"Provider {provider_id} not found in configuration, did you configure it?"
            )
        return provider_config
