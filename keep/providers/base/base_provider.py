"""
Base class for all providers.
"""

import abc
import copy
import datetime
import hashlib
import itertools
import json
import logging
import operator
import os
import re
import uuid
from typing import Literal, Optional

import opentelemetry.trace as trace
import requests

from keep.api.bl.enrichments_bl import EnrichmentsBl
from keep.api.core.db import (
    get_custom_deduplication_rule,
    get_enrichments,
    get_provider_by_name,
    is_linked_provider,
)
from keep.api.logging import ProviderLoggerAdapter
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus, IncidentDto
from keep.api.models.db.alert import ActionType
from keep.api.models.db.topology import TopologyServiceInDto
from keep.api.utils.enrichment_helpers import parse_and_enrich_deleted_and_assignees
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

tracer = trace.get_tracer(__name__)


class BaseProvider(metaclass=abc.ABCMeta):
    OAUTH2_URL = None
    PROVIDER_SCOPES: list[ProviderScope] = []
    PROVIDER_METHODS: list[ProviderMethod] = []
    FINGERPRINT_FIELDS: list[str] = []
    PROVIDER_COMING_SOON = False  # tb: if the provider is coming soon, we show it in the UI but don't allow it to be added
    PROVIDER_CATEGORY: list[
        Literal[
            "Monitoring",
            "Incident Management",
            "Cloud Infrastructure",
            "Ticketing",
            "Identity",
            "Developer Tools",
            "Database",
            "Identity and Access Management",
            "Security",
            "Collaboration",
            "Organizational Tools",
            "CRM",
            "Queues",
            "Others",
        ]
    ] = [
        "Others"
    ]  # tb: Default category for providers that don't declare a category
    PROVIDER_TAGS: list[
        Literal["alert", "ticketing", "messaging", "data", "queue", "topology"]
    ] = []
    WEBHOOK_INSTALLATION_REQUIRED = False  # webhook installation is required for this provider, making it required in the UI

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
        webhooke_template: Optional[str] = None,
        webhook_description: Optional[str] = None,
        webhook_markdown: Optional[str] = None,
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
        self.webhook_markdown = webhook_markdown
        self.provider_description = provider_description
        self.context_manager = context_manager

        # Initialize the logger with our custom adapter
        base_logger = logging.getLogger(self.provider_id)
        # If logs should be stored on the DB, use the custom adapter
        if os.environ.get("KEEP_STORE_PROVIDER_LOGS", "false").lower() == "true":
            self.logger = ProviderLoggerAdapter(
                base_logger, self, context_manager.tenant_id, provider_id
            )
        else:
            self.logger = base_logger

        self.logger.setLevel(
            os.environ.get(
                "KEEP_{}_PROVIDER_LOG_LEVEL".format(self.provider_id.upper()),
                os.environ.get("LOG_LEVEL", "INFO"),
            )
        )

        self.validate_config()
        self.logger.debug(
            "Base provider initialized", extra={"provider": self.__class__.__name__}
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
        if not enrich_alert or results is None:
            return results if results else None

        audit_enabled = bool(kwargs.get("audit_enabled", True))

        self._enrich_alert(enrich_alert, results, audit_enabled=audit_enabled)
        return results

    def _enrich_alert(self, enrichments, results, audit_enabled=True):
        """
        Enrich alert with provider specific data.

        """
        self.logger.debug("Extracting the fingerprint from the alert")
        event = None
        if "fingerprint" in results:
            fingerprint = results["fingerprint"]
        elif self.context_manager.foreach_context.get("value", {}):
            foreach_context: dict | tuple = self.context_manager.foreach_context.get(
                "value", {}
            )
            if isinstance(foreach_context, tuple):
                # This is when we are in a foreach context that is zipped
                foreach_context: dict = foreach_context[0]
                event = foreach_context

            if isinstance(foreach_context, AlertDto):
                fingerprint = foreach_context.fingerprint
            else:
                fingerprint = foreach_context.get("fingerprint")
        # else, if we are in an event context, use the event fingerprint
        elif self.context_manager.event_context:
            # TODO: map all casses event_context is dict and update them to the DTO
            #       and remove this if statement
            event = self.context_manager.event_context
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

        _enrichments = {}
        disposable_enrichments = {}
        # enrich only the requested fields
        for enrichment in enrichments:
            try:
                value = enrichment["value"]
                disposable = bool(enrichment.get("disposable", False))
                if value.startswith("results."):
                    val = enrichment["value"].replace("results.", "")
                    parts = val.split(".")
                    r = copy.copy(results)
                    for part in parts:
                        r = r[part]
                    value = r
                if disposable:
                    disposable_enrichments[enrichment["key"]] = value
                else:
                    _enrichments[enrichment["key"]] = value
                if event is not None:
                    if isinstance(event, dict):
                        event[enrichment["key"]] = value
                    else:
                        setattr(event, enrichment["key"], value)
            except Exception:
                self.logger.error(
                    f"Failed to enrich alert - enrichment: {enrichment}",
                    extra={"fingerprint": fingerprint, "provider": self.provider_id},
                )
                continue
        self.logger.info("Enriching alert", extra={"fingerprint": fingerprint})
        try:
            enrichments_bl = EnrichmentsBl(self.context_manager.tenant_id)
            enrichment_string = ""
            for key, value in _enrichments.items():
                enrichment_string += f"{key}={value}, "
            # remove the last comma
            enrichment_string = enrichment_string[:-2]
            # enrich the alert with _enrichments
            enrichments_bl.enrich_entity(
                fingerprint,
                _enrichments,
                action_type=ActionType.WORKFLOW_ENRICH,  # shahar: todo: should be specific, good enough for now
                action_callee="system",
                action_description=f"Workflow enriched the alert with {enrichment_string}",
                audit_enabled=audit_enabled,
            )
            # enrich with disposable enrichments
            enrichment_string = ""
            for key, value in disposable_enrichments.items():
                enrichment_string += f"{key}={value}, "
            # remove the last comma
            enrichment_string = enrichment_string[:-2]
            enrichments_bl.enrich_entity(
                fingerprint,
                disposable_enrichments,
                action_type=ActionType.WORKFLOW_ENRICH,
                action_callee="system",
                action_description=f"Workflow enriched the alert with {enrichment_string}",
                dispose_on_new_alert=True,
                audit_enabled=audit_enabled,
            )

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
        self.results.append(results)
        # now add the type of the results to the global context
        if results and isinstance(results, list):
            self.context_manager.dependencies.add(results[0].__class__)
        elif results:
            self.context_manager.dependencies.add(results.__class__)

        enrich_alert = kwargs.get("enrich_alert", [])
        if enrich_alert:
            audit_enabled = bool(kwargs.get("audit_enabled", True))
            self._enrich_alert(enrich_alert, results, audit_enabled=audit_enabled)
        # and return the results
        return results

    @staticmethod
    def _format_alert(
        event: dict | list[dict], provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an incoming alert.

        Args:
            event (dict): The raw provider event payload.

        Raises:
            NotImplementedError: For providers who does not implement this method.

        Returns:
            AlertDto | list[AlertDto]: The formatted alert(s).
        """
        raise NotImplementedError("format_alert() method not implemented")

    @classmethod
    def format_alert(
        cls,
        event: dict | list[dict],
        tenant_id: str | None,
        provider_type: str | None,
        provider_id: str | None,
    ) -> AlertDto | list[AlertDto] | None:
        logger = logging.getLogger(__name__)

        provider_instance: BaseProvider | None = None
        if provider_id and provider_type and tenant_id:
            try:
                if is_linked_provider(tenant_id, provider_id):
                    logger.debug(
                        "Provider is linked, skipping loading provider instance"
                    )
                    provider_instance = None
                else:
                    # To prevent circular imports
                    from keep.providers.providers_factory import ProvidersFactory

                    provider_instance: BaseProvider = (
                        ProvidersFactory.get_installed_provider(
                            tenant_id, provider_id, provider_type
                        )
                    )
            except Exception:
                logger.exception(
                    "Failed loading provider instance although all parameters were given",
                    extra={
                        "tenant_id": tenant_id,
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                    },
                )
        logger.debug("Formatting alert")
        formatted_alert = cls._format_alert(event, provider_instance)
        if formatted_alert is None:
            logger.debug(
                "Provider returned None, which means it decided not to format the alert"
            )
            return None
        logger.debug("Alert formatted")
        # after the provider calculated the default fingerprint
        #   check if there is a custom deduplication rule and apply
        custom_deduplication_rule = get_custom_deduplication_rule(
            tenant_id=tenant_id,
            provider_id=provider_id,
            provider_type=provider_type,
        )

        if not isinstance(formatted_alert, list):
            formatted_alert.providerId = provider_id
            formatted_alert.providerType = provider_type
            formatted_alert = [formatted_alert]

        else:
            for alert in formatted_alert:
                alert.providerId = provider_id
                alert.providerType = provider_type

        # if there is no custom deduplication rule, return the formatted alert
        if not custom_deduplication_rule:
            return formatted_alert
        # if there is a custom deduplication rule, apply it
        # apply the custom deduplication rule to calculate the fingerprint
        for alert in formatted_alert:
            logger.info(
                "Applying custom deduplication rule",
                extra={
                    "tenant_id": tenant_id,
                    "provider_id": provider_id,
                    "alert_id": alert.id,
                },
            )
            alert.fingerprint = cls.get_alert_fingerprint(
                alert, custom_deduplication_rule.fingerprint_fields
            )
        return formatted_alert

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
            keys = fingerprint_field.split(".")
            fingerprint_field_value = event_dict
            for key in keys:
                if isinstance(fingerprint_field_value, dict):
                    fingerprint_field_value = fingerprint_field_value.get(key, None)
                else:
                    fingerprint_field_value = None
                    break
            if isinstance(fingerprint_field_value, (list, dict)):
                fingerprint_field_value = json.dumps(fingerprint_field_value)
            if fingerprint_field_value is not None:
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

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from the provider.
        """
        raise NotImplementedError("get_alerts() method not implemented")

    def get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from the provider.
        """
        with tracer.start_as_current_span(f"{self.__class__.__name__}-get_alerts"):
            alerts = self._get_alerts()
            # enrich alerts with provider id
            for alert in alerts:
                alert.providerId = self.provider_id
                alert.providerType = self.provider_type
            return alerts

    def get_alerts_by_fingerprint(self, tenant_id: str) -> dict[str, list[AlertDto]]:
        """
        Get alerts from the provider grouped by fingerprint, sorted by lastReceived.

        Returns:
            dict[str, list[AlertDto]]: A dict of alerts grouped by fingerprint, sorted by lastReceived.
        """
        try:
            alerts = self.get_alerts()
        except NotImplementedError:
            return {}

        if not alerts:
            return {}

        # get alerts, group by fingerprint and sort them by lastReceived
        with tracer.start_as_current_span(f"{self.__class__.__name__}-get_last_alerts"):
            get_attr = operator.attrgetter("fingerprint")
            grouped_alerts = {
                fingerprint: list(alerts)
                for fingerprint, alerts in itertools.groupby(
                    sorted(
                        alerts,
                        key=get_attr,
                    ),
                    get_attr,
                )
            }

        # enrich alerts
        with tracer.start_as_current_span(f"{self.__class__.__name__}-enrich_alerts"):
            pulled_alerts_enrichments = get_enrichments(
                tenant_id=tenant_id,
                fingerprints=grouped_alerts.keys(),
            )
            for alert_enrichment in pulled_alerts_enrichments:
                if alert_enrichment:
                    alerts_to_enrich = grouped_alerts.get(
                        alert_enrichment.alert_fingerprint
                    )
                    for alert_to_enrich in alerts_to_enrich:
                        parse_and_enrich_deleted_and_assignees(
                            alert_to_enrich, alert_enrichment.enrichments
                        )
                        for enrichment in alert_enrichment.enrichments:
                            # set the enrichment
                            setattr(
                                alert_to_enrich,
                                enrichment,
                                alert_enrichment.enrichments[enrichment],
                            )

        return grouped_alerts

    def setup_webhook(
        self, tenant_id: str, keep_api_url: str, api_key: str, setup_alerts: bool = True
    ) -> dict | None:
        """
        Setup a webhook for the provider.

        Args:
            tenant_id (str): _description_
            keep_api_url (str): _description_
            api_key (str): _description_
            setup_alerts (bool, optional): _description_. Defaults to True.

        Returns:
            dict | None: If some secrets needs to be saved, return them in a dict.

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("setup_webhook() method not implemented")

    def clean_up(self):
        """
        Clean up the provider.

        Raises:s
            NotImplementedError: for providers who does not implement this method.
        """
        raise NotImplementedError("clean_up() method not implemented")

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
    def parse_event_raw_body(raw_body: bytes | dict) -> dict:
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
            status=alert_data.get("status", AlertStatus.FIRING),
            lastReceived=alert_data.get(
                "lastReceived",
                datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            ),
            environment=alert_data.get("environment", "alert-from-event-queue"),
            isDuplicate=alert_data.get("isDuplicate", False),
            duplicateReason=alert_data.get("duplicateReason", None),
            service=alert_data.get("service", "alert-from-event-queue"),
            source=alert_data.get("source", [self.provider_type]),
            message=alert_data.get("message", "alert-from-event-queue"),
            description=alert_data.get("description", "alert-from-event-queue"),
            severity=alert_data.get("severity", AlertSeverity.INFO),
            pushed=alert_data.get("pushed", False),
            event_id=alert_data.get("event_id", str(uuid.uuid4())),
            url=alert_data.get("url", None),
            fingerprint=alert_data.get("fingerprint", None),
            providerId=self.provider_id,
        )
        # push the alert to the provider
        url = f'{os.environ["KEEP_API_URL"]}/alerts/event'
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": self.context_manager.api_key,
        }
        response = requests.post(
            url,
            json=alert_model.dict(),
            headers=headers,
            params={"provider_id": self.provider_id},
        )
        try:
            response.raise_for_status()
            self.logger.info("Alert pushed successfully")
        except Exception:
            self.logger.error(
                f"Failed to push alert to {self.provider_id}: {response.content}"
            )

    @classmethod
    def simulate_alert(cls) -> dict:
        # can be overridden by the provider
        import importlib
        import random

        module_path = ".".join(cls.__module__.split(".")[0:-1]) + ".alerts_mock"
        module = importlib.import_module(module_path)

        ALERTS = getattr(module, "ALERTS", None)

        alert_type = random.choice(list(ALERTS.keys()))
        alert_data = ALERTS[alert_type]

        # Start with the base payload
        simulated_alert = alert_data["payload"].copy()

        return simulated_alert

    @property
    def is_installed(self) -> bool:
        """
        Check if provider has been recorded in the database.
        """
        provider = get_provider_by_name(
            self.context_manager.tenant_id, self.config.name
        )
        return provider is not None

    @property
    def is_provisioned(self) -> bool:
        """
        Check if provider exist in env provisioning.
        """
        from keep.parser.parser import Parser

        parser = Parser()
        parser._parse_providers_from_env(self.context_manager)
        return self.config.name in self.context_manager.providers_context


class BaseTopologyProvider(BaseProvider):
    def pull_topology(self) -> tuple[list[TopologyServiceInDto], dict]:
        raise NotImplementedError("get_topology() method not implemented")


class BaseIncidentProvider(BaseProvider):
    def _get_incidents(self) -> list[IncidentDto]:
        raise NotImplementedError("_get_incidents() in not implemented")

    def get_incidents(self) -> list[IncidentDto]:
        return self._get_incidents()

    @staticmethod
    def _format_incident(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> IncidentDto | list[IncidentDto]:
        raise NotImplementedError("_format_incidents() not implemented")

    @classmethod
    def format_incident(
        cls,
        event: dict,
        tenant_id: str | None,
        provider_type: str | None,
        provider_id: str | None,
    ) -> IncidentDto | list[IncidentDto]:
        logger = logging.getLogger(__name__)

        provider_instance: BaseProvider | None = None
        if provider_id and provider_type and tenant_id:
            try:
                # To prevent circular imports
                from keep.providers.providers_factory import ProvidersFactory

                provider_instance: BaseProvider = (
                    ProvidersFactory.get_installed_provider(
                        tenant_id, provider_id, provider_type
                    )
                )
            except Exception:
                logger.exception(
                    "Failed loading provider instance although all parameters were given",
                    extra={
                        "tenant_id": tenant_id,
                        "provider_id": provider_id,
                        "provider_type": provider_type,
                    },
                )
        logger.debug("Formatting Incident")
        return cls._format_incident(event, provider_instance)

    def setup_incident_webhook(
        self,
        tenant_id: str,
        keep_api_url: str,
        api_key: str,
        setup_alerts: bool = True,
    ) -> dict | None:
        """
        Setup a webhook for the provider.

        Args:
            tenant_id (str): _description_
            keep_api_url (str): _description_
            api_key (str): _description_
            setup_alerts (bool, optional): _description_. Defaults to True.

        Returns:
            dict | None: If some secrets needs to be saved, return them in a dict.

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("setup_webhook() method not implemented")
