import logging
import os
import typing

import yaml

from keep.action.action import Action
from keep.alert.alert import Alert
from keep.providers.base.base_provider import BaseProvider
from keep.providers.providers_factory import ProvidersFactory
from keep.step.step import Step


class Parser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config = {"providers": {}}

    def parse(self, alert_file: str, providers_directory: str = None) -> Alert:
        # Parse the alert YAML
        parsed_alert_yaml = self._parse_alerts_file_to_dict(alert_file)
        # Parse the providers (from the alert yaml or from the providers directory)
        providers = self._parse_providers_config(parsed_alert_yaml, providers_directory)
        self.providers = {provider.provider_id: provider for provider in providers}
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
            providers_config=self.config["providers"],
        )
        self.logger.debug("Alert parsed successfully")
        return alert

    def _parse_providers_config(
        self, alert: dict, providers_directory: str
    ) -> typing.List[BaseProvider]:
        self.logger.debug("Parsing providers")
        providers = []
        if providers_directory:
            providers += self._parse_providers_from_providers_dir(providers_directory)

        if alert.get("provider"):
            providers += self._parse_providers_from_alert(alert)

        return providers

    def _parse_providers_from_alert(self, alert: dict) -> typing.List[BaseProvider]:
        providers = []
        for provider in alert.get("provider"):
            provider_id = provider.get("id")
            self.config["providers"][provider_id] = provider
        self.logger.debug("Providers parsed successfully")
        return providers

    def _parse_providers_from_providers_dir(
        self, alert: dict, providers_directory: str
    ) -> typing.List[BaseProvider]:
        providers = []
        for provider_file in os.listdir(providers_directory):
            provider_file_path = os.path.join(providers_directory, provider_file)
            with open(provider_file_path, "r") as file:
                try:
                    provider = yaml.safe_load(file)
                except yaml.YAMLError as e:
                    self.logger.error(f"Error parsing {provider_file_path}: {e}")
                    raise e
            provider_id = provider.get("id")
            self.config["providers"][provider_id] = provider

        self.logger.debug("Providers config parsed successfully")
        return providers

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
            provider_parameters = _step.get("provider")
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
        step_provider_config = step_provider.pop("config")
        step_provider_type = step_provider.pop("type")
        provider_config = self._get_provider_config(step_provider_config)
        provider = ProvidersFactory.get_provider(step_provider_type, provider_config)
        return provider

    def _parse_actions(self, alert) -> typing.List[Action]:
        self.logger.debug("Parsing actions")
        alert_actions = alert.get("actions", [])
        alert_actions_parsed = []
        for _action in alert_actions:
            name = _action.get("name")
            context = _action.get("context")
            provider_config = _action.get("provider").get("config")
            provider_with_config = _action.get("provider").get("with")
            provider_config = self._get_provider_config(provider_config)
            provider_type = _action.get("provider").get("type")
            provider = ProvidersFactory.get_provider(
                provider_type, provider_config, **provider_with_config
            )
            action = Action(
                name=name,
                context=context,
                provider=provider,
                provider_action_config=provider_with_config,
            )
            alert_actions_parsed.append(action)
        self.logger.debug("Actions parsed successfully")
        return alert_actions_parsed

    def _get_provider_config(self, provider_type):
        """Translate {{ <provider_id>.<config_id> }} to a provider config

        Args:
            provider_type (_type_): _description_

        Raises:
            ValueError: _description_
        """
        provider_type = provider_type.split(".")
        if len(provider_type) != 2:
            raise ValueError(
                "Provider config is not valid, should be in the format: {{ <provider_id>.<config_id> }}"
            )

        provider_id = provider_type[1].replace("}}", "").strip()
        provider_config = self.config.get("providers").get(provider_id)
        if not provider_config:
            raise ValueError(
                f"Provider {provider_id} not found in configuration, did you configure it?"
            )
        return provider_config
