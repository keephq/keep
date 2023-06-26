import io
import json
import logging
import os
import typing

import requests
import validators
import yaml

from keep.alert.alert import Alert
from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.providers.base.base_provider import BaseProvider
from keep.providers.providers_factory import ProvidersFactory
from keep.step.step import Step, StepType


class Parser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.context_manager = ContextManager.get_instance()
        self.io_handler = IOHandler()

    def parse(
        self, alert_source: str, providers_file: str = None
    ) -> typing.List[Alert]:
        """_summary_

        Args:
            alert_source (str): could be a url or a file path
            providers_file (str, optional): _description_. Defaults to None.

        Returns:
            typing.List[Alert]: _description_
        """
        # Parse the alert YAML
        parsed_alert_yaml = self._parse_alert_to_dict(alert_source)
        # Parse the providers (from the alert yaml or from the providers directory)
        self.load_providers_config(parsed_alert_yaml, providers_file)
        # Parse the alert itself
        if parsed_alert_yaml.get("alerts"):
            alerts = [
                self._parse_alert(alert, alert_source=alert_source)
                for alert in parsed_alert_yaml.get("alerts")
            ]
        else:
            alert = self._parse_alert(
                parsed_alert_yaml.get("alert"), alert_source=alert_source
            )
            alerts = [alert]
        return alerts

    def _parse_alert_to_dict(self, alert_path: str) -> dict:
        """
        Parse an alert to a dictionary from either a file or a URL.

        Args:
            alert_path (str): a URL or a file path

        Returns:
            dict: Dictionary with the alert information
        """
        self.logger.debug("Parsing alert")
        # If the alert is a URL, get the alert from the URL
        if validators.url(alert_path) is True:
            response = requests.get(alert_path)
            return self._parse_alert_from_stream(io.StringIO(response.text))
        else:
            # else, get the alert from the file
            with open(alert_path, "r") as file:
                return self._parse_alert_from_stream(file)

    def _parse_alert_from_stream(self, stream) -> dict:
        """
        Parse an alert from an IO stream.

        Args:
            stream (IOStream): The stream to read from

        Raises:
            e: If the stream is not a valid YAML

        Returns:
            dict: Dictionary with the alert information
        """
        self.logger.debug("Parsing alert")
        try:
            alert = yaml.safe_load(stream)
        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing alert: {e}")
            raise e
        return alert

    def _parse_alert(self, alert: dict, alert_source: str) -> Alert:
        self.logger.debug("Parsing alert")
        alert_id = self._parse_id(alert)
        alert_owners = self._parse_owners(alert)
        alert_tags = self._parse_tags(alert)
        alert_steps = self._parse_steps(alert)
        alert_actions = self._parse_actions(alert)
        on_failure_action = self._get_on_failure_action(alert)
        alert = Alert(
            alert_id=alert_id,
            alert_source=alert_source,
            alert_owners=alert_owners,
            alert_tags=alert_tags,
            alert_steps=alert_steps,
            alert_actions=alert_actions,
            on_failure=on_failure_action,
        )
        self.logger.debug("Alert parsed successfully")
        return alert

    def load_providers_config(self, alert: dict, providers_file: str):
        self.logger.debug("Parsing providers")
        if providers_file and os.path.exists(providers_file):
            self._parse_providers_from_file(providers_file)

        if alert.get("providers"):
            self._parse_providers_from_alert(alert)

        self._parse_providers_from_env()
        self.logger.debug("Providers parsed and loaded successfully")

    def _parse_providers_from_env(self):
        """
        Parse providers from the KEEP_PROVIDERS environment variables.
            Either KEEP_PROVIDERS to load multiple providers or KEEP_PROVIDER_<provider_name> can be used.

        KEEP_PROVIDERS is a JSON string of the providers config.
            (e.g. {"slack-prod": {"authentication": {"webhook_url": "https://hooks.slack.com/services/..."}}})
        """
        providers_json = os.environ.get("KEEP_PROVIDERS")
        if providers_json:
            try:
                self.logger.debug(
                    "Parsing providers from KEEP_PROVIDERS environment variable"
                )
                self.context_manager.providers_context.update(
                    json.loads(providers_json)
                )
                self.logger.debug(
                    "Providers parsed successfully from KEEP_PROVIDERS environment variable"
                )
            except json.JSONDecodeError:
                self.logger.error(
                    "Error parsing providers from KEEP_PROVIDERS environment variable"
                )

        for env in os.environ.keys():
            if env.startswith("KEEP_PROVIDER_"):
                # KEEP_PROVIDER_SLACK_PROD
                provider_name = (
                    env.replace("KEEP_PROVIDER_", "").replace("_", "-").lower()
                )
                try:
                    self.logger.debug(f"Parsing provider {provider_name} from {env}")
                    # {'authentication': {'webhook_url': 'https://hooks.slack.com/services/...'}}
                    provider_config = json.loads(os.environ.get(env))
                    self.context_manager.providers_context[
                        provider_name
                    ] = provider_config
                    self.logger.debug(
                        f"Provider {provider_name} parsed successfully from {env}"
                    )
                except json.JSONDecodeError:
                    self.logger.error(
                        f"Error parsing provider config from environment variable {env}"
                    )

    def _parse_providers_from_alert(self, alert: dict) -> typing.List[BaseProvider]:
        self.context_manager.providers_context.update(alert.get("providers"))
        self.logger.debug("Alert providers parsed successfully")

    def _parse_providers_from_file(self, providers_file: str):
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
                step_type=StepType.STEP,
            )
            alerts_steps_parsed.append(step)
        self.logger.debug("Steps parsed successfully")
        return alerts_steps_parsed

    def _get_step_provider(self, _step: dict) -> dict:
        step_provider = _step.get("provider")
        step_provider_type = step_provider.pop("type")
        try:
            step_provider_config = step_provider.pop("config")
        except KeyError:
            step_provider_config = {"authentication": {}}
        provider_id, provider_config = self._parse_provider_config(
            step_provider_type, step_provider_config
        )
        provider = ProvidersFactory.get_provider(
            provider_id, step_provider_type, provider_config
        )
        return provider

    def _get_action(self, action: dict, action_name: str | None = None) -> Step:
        name = action_name or action.get("name")
        provider_config = action.get("provider").get("config")
        provider_context = action.get("provider").get("with", {})
        provider_type = action.get("provider").get("type")
        provider_id, provider_config = self._parse_provider_config(
            provider_type, provider_config
        )
        provider = ProvidersFactory.get_provider(
            provider_id, provider_type, provider_config, **provider_context
        )
        action = Step(
            name=name,
            provider=provider,
            config=action,
            provider_context=provider_context,
            step_type=StepType.ACTION,
        )
        return action

    def _parse_actions(self, alert) -> typing.List[Step]:
        self.logger.debug("Parsing actions")
        alert_actions = alert.get("actions", [])
        alert_actions_parsed = []
        for _action in alert_actions:
            parsed_action = self._get_action(_action)
            alert_actions_parsed.append(parsed_action)
        self.logger.debug("Actions parsed successfully")
        return alert_actions_parsed

    def _get_on_failure_action(self, alert) -> Step | None:
        """
        Parse the on-failure action

        Args:
            alert (_type_): _description_

        Returns:
            Action | None: _description_
        """
        self.logger.debug("Parsing on-faliure")
        alert_on_failure = alert.get("on-failure", {})
        if alert_on_failure:
            parsed_action = self._get_action(alert_on_failure, "on-faliure")
            self.logger.debug("Parsed on-failure successfully")
            return parsed_action
        self.logger.debug("No on-failure action")

    def _extract_provider_id(self, provider_type: str):
        """
        Translate {{ <provider_id>.<config_id> }} to a provider id

        Args:
            provider_type (str): _description_

        Raises:
            ValueError: _description_

        Returns:
            _type_: _description_
        """
        # TODO FIX THIS SHIT
        provider_type = provider_type.split(".")
        if len(provider_type) != 2:
            raise ValueError(
                "Provider config is not valid, should be in the format: {{ <provider_id>.<config_id> }}"
            )

        provider_id = provider_type[1].replace("}}", "").strip()
        return provider_id

    def _parse_provider_config(
        self, provider_type: str, provider_config: str | dict | None
    ) -> tuple:
        """
        Parse provider config.
            If the provider config is a dict, return it as is.
            If the provider config is None, return an empty dict.
            If the provider config is a string, extract the config from the providers context.
            * When provider config is either dict or None, provider config id is the same as the provider type.

        Args:
            provider_type (str): The provider type
            provider_config (str | dict | None): The provider config

        Raises:
            ValueError: When the provider config is a string and the provider config id is not found in the providers context.

        Returns:
            tuple: provider id and provider parsed config
        """
        # Support providers without config such as logfile or mock
        if isinstance(provider_config, dict):
            return provider_type, provider_config
        elif provider_config is None:
            return provider_type, {"authentication": {}}
        # extract config when using {{ <provider_id>.<config_id> }}
        elif isinstance(provider_config, str):
            config_id = self._extract_provider_id(provider_config)
            provider_config = self.context_manager.providers_context.get(config_id)
            if not provider_config:
                self.logger.warning(
                    f"Provider {config_id} not found in configuration, did you configure it?"
                )
                provider_config = {"authentication": {}}
            return config_id, provider_config
