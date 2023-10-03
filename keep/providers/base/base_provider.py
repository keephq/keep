"""
Base class for all providers.
"""
import abc
import logging
import re
from dataclasses import field
from typing import Optional

from pydantic.dataclasses import dataclass

from keep.api.core.db import enrich_alert
from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


class BaseProvider(metaclass=abc.ABCMeta):
    OAUTH2_URL = None
    PROVIDER_SCOPES: list[ProviderScope] = []

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
        webhooke_template: Optional[str] = None,
        webhook_description: Optional[str] = None,
        provider_description: Optional[str] = None,
    ):
        """
        Initialize a provider.

        Args:
            provider_id (str): The provider id.
            **kwargs: Provider configuration loaded from the provider yaml file.
        """
        self.provider_id = provider_id

        self.config = config
        self.webhooke_template = webhooke_template
        self.webhook_description = webhook_description
        self.provider_description = provider_description
        self.context_manager = context_manager
        self.logger = context_manager.get_logger()
        self.validate_config()
        self.logger.debug(
            "Base provider initalized", extra={"provider": self.__class__.__name__}
        )
        self.provider_type = self._extract_type()

    def _extract_type(self):
        """
        Extract the provider type from the provider class name.

        Returns:
            str: The provider type.
        """
        name = self.__class__.__name__
        name_without_provider = name.replace("Provider", "")
        name_with_spaces = (
            re.sub("([A-Z])", r" \1", name_without_provider).lower().strip()
        )
        return name_with_spaces.replace(" ", ".")

    @abc.abstractmethod
    def dispose(self):
        """
        Dispose of the provider.
        """
        raise NotImplementedError("dispose() method not implemented")

    @abc.abstractmethod
    def validate_config():
        """
        Validate provider configuration.
        """
        raise NotImplementedError("validate_config() method not implemented")

    def notify(self, **kwargs):
        """
        Output alert message.

        Args:
            **kwargs (dict): The provider context (with statement)
        """
        # trigger the provider
        results = self._notify(**kwargs)
        # if the alert should be enriched, enrich it
        enrich_alert = kwargs.get("enrich_alert", [])
        if not enrich_alert:
            return results

        if not results:
            return

        # Now try to enrich the alert
        if "fingerprint" in results:
            fingerprint = results["fingerprint"]
        # else, if we are in an event context, use the event fingerprint
        elif self.context_manager.event_context:
            fingerprint = self.context_manager.event_context.fingerprint
        else:
            raise Exception(
                "No fingerprint found for alert enrichment",
                extra={"provider": self.provider_id},
            )
        self._enrich_alert(fingerprint, enrich_alert, results)
        return results

    def _enrich_alert(self, fingerprint, enrichments, results):
        """
        Enrich alert with provider specific data.

        """
        _enrichments = {}
        # enrich only the requested fields
        for enrichment in enrichments:
            try:
                if enrichment["value"].startswith("results."):
                    val = enrichment["value"].replace("results.", "")
                    _enrichments[enrichment["key"]] = results[val]
                else:
                    _enrichments[enrichment["key"]] = enrichment["value"]
            except Exception as e:
                self.logger.error(
                    "Failed to enrich alert",
                    extra={"fingerprint": fingerprint, "provider": self.provider_id},
                )
                continue
        self.logger.info("Enriching alert", extra={"fingerprint": fingerprint})
        try:
            enrich_alert(self.context_manager.tenant_id, fingerprint, _enrichments)
        except Exception as e:
            self.logger.error(
                "Failed to enrich alert",
                extra={"fingerprint": fingerprint, "provider": self.provider_id},
            )
            raise e
        self.logger.info("Alert enriched", extra={"fingerprint": fingerprint})

    def _notify(self, **kwargs):
        """
        Output alert message.

        Args:
            **kwargs (dict): The provider context (with statement)
        """
        raise NotImplementedError("notify() method not implemented")

    def _query(self, **kwargs: dict):
        """
        Query the provider using the given query

        Args:
            kwargs (dict): The provider context (with statement)

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("query() method not implemented")

    def query(self, **kwargs: dict):
        # just run the query
        results = self._query(**kwargs)
        # now add the type of the results to the global context
        if results and type(results) == list:
            self.context_manager.dependencies.add(results[0].__class__)
        elif results:
            self.context_manager.dependencies.add(results.__class__)
        # and return the results
        return results

    @staticmethod
    def format_alert(event: dict) -> AlertDto | list[AlertDto]:
        raise NotImplementedError("format_alert() method not implemented")

    def get_alerts_configuration(self, alert_id: Optional[str] = None):
        """
        Get configuration of alerts from the provider.

        Args:
            alert_id (Optional[str], optional): If given, gets a specific alert by id. Defaults to None.
        """
        # todo: we'd want to have a common alert model for all providers (also for consistent output from GPT)
        raise NotImplementedError("get_alerts() method not implemented")

    def deploy_alert(self, alert: dict, alert_id: Optional[str] = None):
        """
        Deploy an alert to the provider.

        Args:
            alert (dict): The alert to deploy.
            alert_id (Optional[str], optional): If given, deploys a specific alert by id. Defaults to None.
        """
        raise NotImplementedError("deploy_alert() method not implemented")

    def get_alerts(self):
        """
        Get alerts from the provider.
        """
        raise NotImplementedError("get_alerts() method not implemented")

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ):
        """
        Setup a webhook for the provider.

        Args:
            tenant_id (str): _description_
            keep_api_url (str): _description_
            api_key (str): _description_
            setup_alerts (bool, optional): _description_. Defaults to True.

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("setup_webhook() method not implemented")

    @staticmethod
    def get_alert_schema() -> dict:
        """
        Get the alert schema description for the provider.
            e.g. How to define an alert for the provider that can be pushed via the API.

        Returns:
            str: The alert format description.
        """
        raise NotImplementedError(
            "get_alert_format_description() method not implemented"
        )

    @staticmethod
    def oauth2_logic(**payload) -> dict:
        """
        Logic for oauth2 authentication.

        For example, in Slack oauth2, we need to get the code from the payload and exchange it for a token.

        return: dict: The secrets to be saved as the provider configuration. (e.g. the Slack access token)
        """
        raise NotImplementedError("oauth2_logic() method not implemented")

    @staticmethod
    def parse_event_raw_body(raw_body: bytes) -> bytes:
        """
        Parse the raw body of an event and create an ingestable dict from it.

        For instance, in parseable, the "event" is just a string
        > b'Alert: Server side error triggered on teststream1\nMessage: server reporting status as 500\nFailing Condition: status column equal to abcd, 2 times'
        and we want to return an object
        > b"{'alert': 'Server side error triggered on teststream1', 'message': 'server reporting status as 500', 'failing_condition': 'status column equal to abcd, 2 times'}"

        If this method is not implemented for a provider, just return the raw body.

        Args:
            raw_body (bytes): The raw body of the incoming event (/event endpoint in alerts.py)

        Returns:
            dict: Ingestable event
        """
        return raw_body

    def get_logs(self, limit: int = 5) -> list:
        """
        Get logs from the provider.

        Args:
            limit (int): The number of logs to get.
        """
        raise NotImplementedError("get_logs() method not implemented")

    def expose(self):
        """Expose parameters that were calculated during query time.

        Each provider can expose parameters that were calculated during query time.
        E.g. parameters that were supplied by the user and were rendered by the provider.

        A concrete example is the "_from" and "to" of the Datadog Provider which are calculated during execution.
        """
        # TODO - implement dynamically using decorators and
        return {}
