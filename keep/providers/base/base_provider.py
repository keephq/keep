"""
Base class for all providers.
"""
import abc
import copy
import datetime
import hashlib
import json
import os
import re
import uuid
from typing import Literal, Optional

import opentelemetry.trace as trace
import requests

from keep.api.core.db import enrich_alert
from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

tracer = trace.get_tracer(__name__)


class BaseProvider(metaclass=abc.ABCMeta):
    OAUTH2_URL = None
    PROVIDER_SCOPES: list[ProviderScope] = []
    PROVIDER_METHODS: list[ProviderMethod] = []
    FINGERPRINT_FIELDS: list[str] = []
    PROVIDER_TAGS: list[
        Literal["alert", "ticketing", "messaging", "data", "queue"]
    ] = []

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
        self.results = []
        # tb: we can have this overriden by customer configuration, when initializing the provider
        self.fingerprint_fields = self.FINGERPRINT_FIELDS

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

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate provider scopes.

        Returns:
            dict: where key is the scope name and value is whether the scope is valid (True boolean) or string with error message.
        """
        return {}

    def notify(self, **kwargs):
        """
        Output alert message.

        Args:
            **kwargs (dict): The provider context (with statement)
        """
        # trigger the provider
        results = self._notify(**kwargs)
        self.results.append(results)
        # if the alert should be enriched, enrich it
        enrich_alert = kwargs.get("enrich_alert", [])
        if not enrich_alert:
            return results

        if not results:
            return

        # Now try to enrich the alert
        self.logger.debug("Extracting the fingerprint from the alert")
        if "fingerprint" in results:
            fingerprint = results["fingerprint"]
        # else, if we are in an event context, use the event fingerprint
        elif self.context_manager.event_context:
            # TODO: map all casses event_context is dict and update them to the DTO
            #       and remove this if statement
            if isinstance(self.context_manager.event_context, dict):
                fingerprint = self.context_manager.event_context.get("fingerprint")
            # Alert DTO
            else:
                fingerprint = self.context_manager.event_context.fingerprint
        else:
            fingerprint = None

        if not fingerprint:
            self.logger.error(
                "No fingerprint found for alert enrichment",
                extra={"provider": self.provider_id},
            )
            raise Exception("No fingerprint found for alert enrichment")
        self.logger.debug("Fingerprint extracted", extra={"fingerprint": fingerprint})
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
                    parts = val.split(".")
                    r = copy.copy(results)
                    for part in parts:
                        r = r[part]
                    _enrichments[enrichment["key"]] = r
                else:
                    _enrichments[enrichment["key"]] = enrichment["value"]
            except Exception:
                self.logger.error(
                    f"Failed to enrich alert - enrichment: {enrichment}",
                    extra={"fingerprint": fingerprint, "provider": self.provider_id},
                )
                continue
        self.logger.info("Enriching alert", extra={"fingerprint": fingerprint})
        try:
            enrich_alert(self.context_manager.tenant_id, fingerprint, _enrichments)
        except Exception as e:
            self.logger.error(
                "Failed to enrich alert in db",
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
        if results and isinstance(results, list):
            self.context_manager.dependencies.add(results[0].__class__)
        elif results:
            self.context_manager.dependencies.add(results.__class__)
        # and return the results
        return results

    @staticmethod
    def format_alert(event: dict) -> AlertDto | list[AlertDto]:
        raise NotImplementedError("format_alert() method not implemented")

    @staticmethod
    def get_alert_fingerprint(alert: AlertDto, fingerprint_fields: list = []) -> str:
        """
        Get the fingerprint of an alert.

        Args:
            event (AlertDto): The alert to get the fingerprint of.
            fingerprint_fields (list, optional): The fields we calculate the fingerprint upon. Defaults to [].

        Returns:
            str: hexdigest of the fingerprint or the event.name if no fingerprint_fields were given.
        """
        if not fingerprint_fields:
            return alert.name
        fingerprint = hashlib.sha256()
        event_dict = alert.dict()
        for fingerprint_field in fingerprint_fields:
            fingerprint_field_value = event_dict.get(fingerprint_field, None)
            if isinstance(fingerprint_field_value, (list, dict)):
                fingerprint_field_value = json.dumps(fingerprint_field_value)
            if fingerprint_field_value:
                fingerprint.update(str(fingerprint_field_value).encode())
        return fingerprint.hexdigest()

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

    def _get_alerts(self):
        """
        Get alerts from the provider.
        """
        raise NotImplementedError("get_alerts() method not implemented")

    def get_alerts(self):
        """
        Get alerts from the provider.
        """
        with tracer.start_as_current_span(f"{self.__class__.__name__}-get_alerts"):
            return self._get_alerts()

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

    def start_consume(self):
        """Get the consumer for the provider.

        should be implemented by the provider if it has a consumer.

        for an example, see Kafka Provider

        Returns:
            Consumer: The consumer for the provider.
        """
        return

    def status(self) -> bool:
        """Return the status of the provider.

        Returns:
            bool: The status of the provider.
        """
        return {
            "status": "should be implemented by the provider if it has a consumer",
            "error": "",
        }

    @property
    def is_consumer(self) -> bool:
        """Return consumer if the inherited class has a start_consume method.

        Returns:
            bool: _description_
        """
        return self.start_consume.__qualname__ != "BaseProvider.start_consume"

    def _push_alert(self, alert: dict):
        """
        Push an alert to the provider.

        Args:
            alert (dict): The alert to push.
        """
        # if this is not a dict, try to convert it to a dict
        if not isinstance(alert, dict):
            try:
                alert_data = json.loads(alert)
            except Exception:
                alert_data = alert_data
        else:
            alert_data = alert

        # if this is still not a dict, we can't push it
        if not isinstance(alert_data, dict):
            self.logger.warning(
                "We currently support only alert represented as a dict, dismissing alert",
                extra={"alert": alert},
            )
            return
        # now try to build the alert model
        # we will have a lot of default values here to support all providers and all cases, the
        # way to fine tune those would be to use the provider specific model or enforce that the event from the queue will be casted into the fields
        alert_model = AlertDto(
            id=alert_data.get("id", str(uuid.uuid4())),
            name=alert_data.get("name", "alert-from-event-queue"),
            status=alert_data.get("status", "alert-from-event-queue"),
            lastReceived=alert_data.get("lastReceived", datetime.datetime.now()),
            environment=alert_data.get("environment", "alert-from-event-queue"),
            isDuplicate=alert_data.get("isDuplicate", False),
            duplicateReason=alert_data.get("duplicateReason", None),
            service=alert_data.get("service", "alert-from-event-queue"),
            source=alert_data.get("source", [self.provider_type]),
            message=alert_data.get("message", "alert-from-event-queue"),
            description=alert_data.get("description", "alert-from-event-queue"),
            severity=alert_data.get("severity", "alert-from-event-queue"),
            fatigueMeter=alert_data.get("fatigueMeter", 0),
            pushed=alert_data.get("pushed", False),
            event_id=alert_data.get("event_id", str(uuid.uuid4())),
            url=alert_data.get("url", None),
            fingerprint=alert_data.get("fingerprint", None),
        )
        # push the alert to the provider
        url = f'{os.environ["KEEP_API_URL"]}/alerts/event'
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": self.context_manager.api_key,
        }
        response = requests.post(url, json=alert_model.dict(), headers=headers)
        try:
            response.raise_for_status()
            self.logger.info("Alert pushed successfully")
        except Exception:
            self.logger.error(
                f"Failed to push alert to {self.provider_id}: {response.content}"
            )
