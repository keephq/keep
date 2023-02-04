import logging
import typing

import yaml

from keep.action.action import Action
from keep.alert.alert import Alert
from keep.providers.provider_factory.provider_factory import ProviderFactory
from keep.step.step import Step


class Parser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse(self, alert_file: str, providers_directory: str = None):
        # Parse the alert YAML
        alert = self._parse_alerts_file_to_dict(alert_file)
        # Parse the providers (from the alert yaml or from the providers directory)
        providers = self._parse_providers(alert, providers_directory)
        # Parse the alert itself
        alert = self._parse_alerts_file_to_dict(alert_file)

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
        alert_actions = self._parse_action(alert)
        alert = Alert(
            alert_id=alert_id,
            alert_owners=alert_owners,
            alert_tags=alert_tags,
            alert_steps=alert_steps,
            alert_actions=alert_actions,
        )
        self.logger.debug("Alert parsed successfully")
        return alert

    def _parse_providers(
        self, alert: dict, providers_directory: str
    ) -> typing.List[Host]:
        self.logger.debug("Parsing hosts")
        if providers_directory:
            providers = self._parse_providers(providers_directory)

        if alert_file.get("provider"):
            providers += self._parse_providers_from_alert(alert)

        return providers

    def _parse_providers_from_alert(self, alert: dict) -> typing.List[Provider]:
        providers = []
        for provider in alert.get("provider"):
            provider = Provider(**provider)
            providers.append(provider)
        self.logger.debug("Providers parsed successfully")
        return providers

    def _parse_providers(self, providers_directory: str) -> typing.List[Provider]:
        providers = []
        for provider_file in os.listdir(providers_directory):
            provider_file_path = os.path.join(providers_directory, provider_file)
            with open(provider_file_path, "r") as file:
                try:
                    provider = yaml.safe_load(file)
                except yaml.YAMLError as e:
                    self.logger.error(f"Error parsing {provider_file_path}: {e}")
                    raise e
            provider = provider_factory.get_provider(provider)
            providers.append(provider)
        self.logger.debug("Providers parsed successfully")
        return providers

    def _parse_id(self, alert) -> str:
        alert_id = alert.get("alert_id")
        if alert_id is None:
            raise ValueError("Alert ID is required")
        return alert_id

    def _parse_owners(self, alert) -> typing.List[str]:
        alert_owners = alert.get("alert_owners", [])
        return alert_owners

    def _parse_tags(self, alert) -> typing.List[str]:
        alert_tags = alert.get("alert_tags", [])
        return alert_tags

    def _parse_steps(self, alert) -> typing.List[Step]:
        self.logger.debug("Parsing steps")
        alert_steps = alert.get("alert_steps", [])
        alerts_steps_parsed = []
        for _step in alert_steps:
            # extract the host
            host = _step.get("from")

            step = Step(**_step)
            alerts_steps_parsed.append(step)
        self.logger.debug("Steps parsed successfully")
        return alerts_steps_parsed

    def _parse_action(self, alert) -> typing.List[Action]:
        self.logger.debug("Parsing actions")
        alert_actions = alert.get("alert_actions", [])
        alert_actions_parsed = []
        for _action in alert_actions:
            action = Action(**_action)
            alert_actions_parsed.append(action)
        self.logger.debug("Actions parsed successfully")
        return alert_actions_parsed
