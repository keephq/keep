import io
import logging
import os
import typing

import requests
import validators
import yaml
from fastapi import HTTPException

from keep.alert.alert import Alert
from keep.contextmanager.contextmanager import ContextManager
from keep.parser.parser import Parser
from keep.providers.providers_factory import ProvidersFactory
from keep.storagemanager.storagemanagerfactory import StorageManagerFactory


class AlertStore:
    # TODO: alert store should be persistent using database and not only "filesystem"
    #       e.g. we should be able to get alerts from a database

    def __init__(self):
        self.parser = Parser()
        self.logger = logging.getLogger(__name__)
        self.storage_manager = StorageManagerFactory.get_file_manager()
        self.context_manager = ContextManager.get_instance()

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
            return self._read_alert_from_stream(io.StringIO(response.text))
        else:
            # else, get the alert from the file
            with open(alert_path, "r") as file:
                return self._read_alert_from_stream(file)

    def get_alert(self, tenant_id: str, alert_id: str) -> Alert:
        # TODO: this should be refactored
        #       we should get alerts from a database
        #       its a patch to get all alerts and look for an id
        #       this is not efficient

        # get specific alert
        alerts = self.get_all_alerts(tenant_id)
        for alert in alerts:
            if alert.alert_id == alert_id:
                return alert

        # If not alert
        raise HTTPException(
            status_code=404,
            detail=f"Alert {alert_id} not found",
        )

    def get_all_alerts(self, tenant_id: str) -> list[Alert]:
        # list all tenant's alerts workflows
        alerts_files = self.storage_manager.get_files(tenant_id)
        self._load_providers_from_installed_providers(tenant_id)
        raw_alerts = []
        for alert in alerts_files:
            try:
                raw_alerts.append(yaml.safe_load(alert))
            except yaml.YAMLError as e:
                self.logger.error(f"Error parsi\ng alert: {e}")
                # TODO handle
                pass

        alerts = []
        for alert in raw_alerts:
            self.logger.info(f"Getting alert {alert}")
            try:
                alerts.extend(self.parser.parse(alert))
                self.logger.info(f"Alert {alert} fetched successfully")
            except Exception as e:
                self.logger.error(
                    f"Error parsing alert {alert}", extra={"exception": e}
                )
        return alerts

    def get_alerts(
        self, alert_path: str | tuple[str], providers_file: str = None
    ) -> list[Alert]:
        # get specific alerts, the original interface
        # to interact with alerts
        alerts = []
        if isinstance(alert_path, tuple):
            for alert_url in alert_path:
                alert_yaml = self._parse_alert_to_dict(alert_url)
                alerts.extend(self.parser.parse(alert_yaml, providers_file))
        elif os.path.isdir(alert_path):
            alerts.extend(self._get_alerts_from_directory(alert_path, providers_file))
        else:
            alert_yaml = self._parse_alert_to_dict(alert_path)
            alerts = self.parser.parse(alert_yaml, providers_file)

        return alerts

    def _get_alerts_from_directory(
        self, alerts_dir: str, providers_file: str = None
    ) -> list[Alert]:
        """
        Run alerts from a directory.

        Args:
            alerts_dir (str): A directory containing alert yamls.
            providers_file (str, optional): The path to the providers yaml. Defaults to None.
        """
        alerts = []
        for file in os.listdir(alerts_dir):
            if file.endswith(".yaml") or file.endswith(".yml"):
                self.logger.info(f"Getting alerts from {file}")
                parsed_alert_yaml = self._parse_alert_to_dict(
                    os.path.join(alerts_dir, file)
                )
                try:
                    alerts.extend(self.parser.parse(parsed_alert_yaml, providers_file))
                    self.logger.info(f"Alert from {file} fetched successfully")
                except Exception as e:
                    self.logger.error(
                        f"Error parsing alert from {file}", extra={"exception": e}
                    )
        return alerts

    def _read_alert_from_stream(self, stream) -> dict:
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

    def _load_providers_from_installed_providers(self, tenant_id: str):
        # TODO: should be refactored and moved to ProvidersManager or something
        # Load installed providers
        installed_providers = ProvidersFactory.get_installed_providers(
            tenant_id=tenant_id
        )
        for provider in installed_providers:
            self.logger.info(f"Loading provider {provider}")
            provider_type, provider_id, provider_config = provider.values()
            provider = ProvidersFactory.get_provider(
                provider_id=provider_id,
                provider_type=provider_type,
                provider_config=provider_config,
            )
            # TODO - should somehow be in DB and map provider id (unique) to provider name (not unique)
            provider_name = provider_config.pop("name")
            self.context_manager.providers_context[provider_name] = provider_config
            self.logger.info(f"Provider {provider} loaded successfully")
