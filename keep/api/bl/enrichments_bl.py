import datetime
import json
import logging
import re
from uuid import UUID

import celpy
import chevron
from fastapi import HTTPException
from sqlalchemy import func
from sqlmodel import Session, select

from keep.api.core.config import config
from keep.api.core.db import enrich_entity as enrich_alert_db
from keep.api.core.db import (
    get_alert_by_event_id,
    get_enrichment_with_session,
    get_mapping_rule_by_id,
    get_session_sync,
    get_topology_data_by_dynamic_matcher,
)
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import ActionType
from keep.api.models.db.enrichment_event import (
    EnrichmentEvent,
    EnrichmentLog,
    EnrichmentStatus,
    EnrichmentType,
)
from keep.api.models.db.extraction import ExtractionRule
from keep.api.models.db.mapping import MappingRule


def get_nested_attribute(obj: AlertDto, attr_path: str):
    """
    Recursively get a nested attribute
    """
    # Special case for source, since it's a list
    if attr_path == "source" and obj.source is not None and len(obj.source) > 0:
        return obj.source[0]

    if isinstance(attr_path, list):
        return (
            all(get_nested_attribute(obj, attr) is not None for attr in attr_path)
            or None
        )

    attributes = attr_path.split(".")
    for attr in attributes:
        # @@ is used as a placeholder for . in cases where the attribute name has a .
        # For example, we have {"results": {"some.attribute": "value"}}
        # We can access it by using "results.some@@attribute" so we won't think its a nested attribute
        if attr is not None and "@@" in attr:
            attr = attr.replace("@@", ".")
        obj = getattr(
            obj,
            attr,
            obj.get(attr, None) if isinstance(obj, dict) else None,
        )
        if obj is None:
            return None
    return obj


class EnrichmentsBl:

    ENRICHMENT_DISABLED = config("KEEP_ENRICHMENT_DISABLED", default="false", cast=bool)

    def __init__(self, tenant_id: str, db: Session | None = None):
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id
        self.__logs: list[EnrichmentLog] = []
        if not EnrichmentsBl.ENRICHMENT_DISABLED:
            self.db_session = db or get_session_sync()
            self.elastic_client = ElasticClient(tenant_id=tenant_id)

    def run_mapping_rule_by_id(self, rule_id: int, alert_id: UUID) -> AlertDto:
        rule = get_mapping_rule_by_id(self.db_session, rule_id, session=self.db_session)
        if not rule:
            raise HTTPException(status_code=404, detail="Mapping rule not found")

        alert = get_alert_by_event_id(
            self.db_session, alert_id, session=self.db_session
        )
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        return self._check_match_rule_and_enrich(alert, rule)

    def run_extraction_rules(
        self, event: AlertDto | dict, pre=False
    ) -> AlertDto | dict:
        """
        Run the extraction rules for the event
        """
        if EnrichmentsBl.ENRICHMENT_DISABLED:
            self.logger.debug("Enrichment is disabled, skipping extraction rules")
            return event

        fingerprint = (
            event.get("fingerprint")
            if isinstance(event, dict)
            else getattr(event, "fingerprint", None)
        )
        event_id = (
            event.get("id") if isinstance(event, dict) else getattr(event, "id", None)
        )
        self._add_enrichment_log(
            "Running extraction rules for incoming event",
            "info",
            {
                "tenant_id": self.tenant_id,
                "fingerprint": fingerprint,
                "event_id": event_id,
                "pre": pre,
            },
        )
        rules: list[ExtractionRule] = (
            self.db_session.query(ExtractionRule)
            .filter(ExtractionRule.tenant_id == self.tenant_id)
            .filter(ExtractionRule.disabled == False)
            .filter(ExtractionRule.pre == pre)
            .order_by(ExtractionRule.priority.desc())
            .all()
        )

        if not rules:
            self._add_enrichment_log(
                "No extraction rules found for tenant",
                "debug",
                {
                    "tenant_id": self.tenant_id,
                    "fingerprint": fingerprint,
                    "event_id": event_id,
                    "pre": pre,
                },
            )
            self._track_enrichment_event(
                event_id, EnrichmentStatus.SKIPPED, EnrichmentType.EXTRACT, 0, {}
            )
            return event

        is_alert_dto = False
        if isinstance(event, AlertDto):
            is_alert_dto = True
            event = json.loads(json.dumps(event.dict(), default=str))

        for rule in rules:
            attribute = rule.attribute
            if (
                attribute.startswith("{{") is False
                and attribute.endswith("}}") is False
            ):
                # Wrap the attribute in {{ }} to make it a valid chevron template
                attribute = f"{{{{ {attribute} }}}}"
            attribute_value = chevron.render(attribute, event)

            if not attribute_value:
                self._add_enrichment_log(
                    "Attribute value is empty, skipping extraction",
                    "info",
                    {"rule_id": rule.id},
                )
                self._track_enrichment_event(
                    event_id,
                    EnrichmentStatus.SKIPPED,
                    EnrichmentType.EXTRACT,
                    rule.id,
                    {},
                )
                continue

            if rule.condition is None or rule.condition == "*" or rule.condition == "":
                self._add_enrichment_log(
                    "No condition specified for the rule, enriching...",
                    "info",
                    {
                        "rule_id": rule.id,
                        "tenant_id": self.tenant_id,
                        "fingerprint": fingerprint,
                    },
                )
            else:
                env = celpy.Environment()
                ast = env.compile(rule.condition)
                prgm = env.program(ast)
                activation = celpy.json_to_cel(event)
                relevant = prgm.evaluate(activation)
                if not relevant:
                    self._add_enrichment_log(
                        f"Condition did not match, skipping extraction for rule {rule.id} with condition {rule.condition}",
                        "debug",
                        {"rule_id": rule.id},
                    )
                    continue
            match_result = re.search(rule.regex, attribute_value)
            if match_result:
                match_dict = match_result.groupdict()
                # we don't override source
                match_dict.pop("source", None)
                event.update(match_dict)
                self._add_enrichment_log(
                    "Event enriched with extraction rule",
                    "info",
                    {
                        "rule_id": rule.id,
                        "tenant_id": self.tenant_id,
                        "fingerprint": fingerprint,
                    },
                )
                self._track_enrichment_event(
                    event_id,
                    EnrichmentStatus.SUCCESS,
                    EnrichmentType.EXTRACT,
                    rule.id,
                    match_dict,
                )
            else:
                self._add_enrichment_log(
                    "Regex did not match, skipping extraction",
                    "info",
                    {
                        "rule_id": rule.id,
                        "tenant_id": self.tenant_id,
                        "fingerprint": fingerprint,
                    },
                )
                self._track_enrichment_event(
                    event_id,
                    EnrichmentStatus.SKIPPED,
                    EnrichmentType.EXTRACT,
                    rule.id,
                    {},
                )

        return AlertDto(**event) if is_alert_dto else event

    def run_mapping_rules(self, alert: AlertDto) -> AlertDto:
        """
        Run the mapping rules for the alert.

        Args:
        - alert (AlertDto): The incoming alert to be processed and enriched.

        Returns:
        - AlertDto: The enriched alert after applying mapping rules.
        """
        if EnrichmentsBl.ENRICHMENT_DISABLED:
            self.logger.debug("Enrichment is disabled, skipping mapping rules")
            return alert

        self._add_enrichment_log(
            "Running mapping rules for incoming alert",
            "info",
            {"fingerprint": alert.fingerprint, "tenant_id": self.tenant_id},
        )

        # Retrieve all active mapping rules for the current tenant, ordered by priority
        rules: list[MappingRule] = (
            self.db_session.query(MappingRule)
            .filter(MappingRule.tenant_id == self.tenant_id)
            .filter(MappingRule.disabled == False)
            .order_by(MappingRule.priority.desc())
            .all()
        )

        if not rules:
            # If no mapping rules are found for the tenant, log and return the original alert
            self._add_enrichment_log(
                "No mapping rules found for tenant",
                "debug",
                {"fingerprint": alert.fingerprint, "tenant_id": self.tenant_id},
            )
            return alert

        for rule in rules:
            self._check_match_rule_and_enrich(alert, rule)

        return alert

    def _check_match_rule_and_enrich(self, alert: AlertDto, rule: MappingRule) -> bool:
        """
        Check if the alert matches the conditions specified in the mapping rule.
        If a match is found, enrich the alert and log the enrichment.

        Args:
        - alert (AlertDto): The incoming alert to be processed.
        - rule (MappingRule): The mapping rule to be checked against.

        Returns:
        - bool: True if alert matches the rule, False otherwise.
        """
        self._add_enrichment_log(
            "Checking alert against mapping rule",
            "debug",
            {"fingerprint": alert.fingerprint, "rule_id": rule.id},
        )

        # Check if the alert has any of the attributes defined in matchers
        match = False
        for matcher in rule.matchers:
            if get_nested_attribute(alert, matcher) is not None:
                self._add_enrichment_log(
                    f"Alert matched a mapping rule for matcher: {matcher}",
                    "debug",
                    {
                        "fingerprint": alert.fingerprint,
                        "rule_id": rule.id,
                        "matcher": matcher,
                    },
                )
                match = True
                break

        if not match:
            self._add_enrichment_log(
                "Alert does not match any of the conditions for the rule",
                "debug",
                {
                    "fingerprint": alert.fingerprint,
                    "rule_id": rule.id,
                    "matchers": rule.matchers,
                    "alert": str(alert),
                },
            )
            self._track_enrichment_event(
                alert.id, EnrichmentStatus.SKIPPED, EnrichmentType.MAPPING, rule.id, {}
            )
            return False

        self._add_enrichment_log(
            "Alert matched a mapping rule, enriching...",
            "info",
            {"fingerprint": alert.fingerprint, "rule_id": rule.id},
        )

        # Apply enrichment to the alert
        enrichments = {}
        if rule.type == "topology":
            matcher_value = {}
            for matcher in rule.matchers:
                matcher_value[matcher] = get_nested_attribute(alert, matcher)
            topology_service = get_topology_data_by_dynamic_matcher(
                self.tenant_id, matcher_value
            )

            if not topology_service:
                self._add_enrichment_log(
                    "No topology service found to match on",
                    "debug",
                    {"matcher_value": matcher_value},
                )
            else:
                enrichments = topology_service.dict(exclude_none=True)
                # repository could be taken from application too
                if not topology_service.repository and topology_service.applications:
                    for application in topology_service.applications:
                        if application.repository:
                            enrichments["repository"] = application.repository
                # Remove redundant fields
                enrichments.pop("tenant_id", None)
                enrichments.pop("id", None)
        elif rule.type == "csv":
            for row in rule.rows:
                if any(
                    self._check_matcher(alert, row, matcher)
                    for matcher in rule.matchers
                ):
                    # Extract enrichments from the matched row
                    enrichments = {}
                    for key, value in row.items():
                        if value is not None:
                            is_matcher = False
                            for matcher in rule.matchers:
                                if key in matcher:
                                    is_matcher = True
                                    break
                            if not is_matcher:
                                # If the key has . (dot) in it, it'll be added as is while it needs to be nested.
                                # @tb: fix when somebody will be complaining about this.
                                enrichments[key.strip()] = value
                    break

        if enrichments:
            # Enrich the alert with the matched data from the row
            for key, value in enrichments.items():
                # It's not relevant to enrich if the value if empty
                if value is not None:
                    setattr(alert, key.strip(), value)

            # Save the enrichments to the database
            # SHAHAR: since when running this enrich_alert, the alert is not in elastic yet (its indexed after),
            #         enrich alert will fail to update the alert in elastic.
            #         hence should_exist = False
            self.enrich_entity(
                alert.fingerprint,
                enrichments,
                action_type=ActionType.MAPPING_RULE_ENRICH,
                action_callee="system",
                action_description=f"Alert enriched with mapping from rule `{rule.name}`",
                should_exist=False,
            )

            self._add_enrichment_log(
                "Alert enriched",
                "info",
                {"fingerprint": alert.fingerprint, "rule_id": rule.id},
            )
            self._track_enrichment_event(
                alert.id,
                EnrichmentStatus.SUCCESS,
                EnrichmentType.MAPPING,
                rule.id,
                enrichments,
            )
            return True  # Exit on first successful enrichment (assuming single match)

        self._add_enrichment_log(
            "Alert was not enriched by mapping rule",
            "info",
            {"rule_id": rule.id, "alert_fingerprint": alert.fingerprint},
        )
        self._track_enrichment_event(
            alert.id,
            EnrichmentStatus.FAILURE,
            EnrichmentType.MAPPING,
            rule.id,
            {},
        )
        return False

    @staticmethod
    def _is_match(value, pattern):
        if value is None or pattern is None:
            return False
        return re.search(pattern, value) is not None

    def _check_matcher(self, alert: AlertDto, row: dict, matcher: list) -> bool:
        """
        Check if the alert matches the conditions specified by a matcher.

        Args:
        - alert (AlertDto): The incoming alert to be processed.
        - row (dict): The row from the mapping rule data to compare against.
        - matcher (str): The matcher string specifying conditions.

        Returns:
        - bool: True if alert matches the matcher, False otherwise.
        """
        try:
            return all(
                self._is_match(
                    get_nested_attribute(alert, attribute.strip()),
                    row.get(attribute.strip()),
                )
                or get_nested_attribute(alert, attribute.strip())
                == row.get(attribute.strip())
                or row.get(attribute.strip()) == "*"  # Wildcard match
                for attribute in matcher
            )
        except TypeError:
            self._add_enrichment_log(
                "Error while checking matcher",
                "error",
                {
                    "fingerprint": alert.fingerprint,
                    "matcher": matcher,
                },
            )
            return False

    def enrich_entity(
        self,
        fingerprint: str,
        enrichments: dict,
        action_type: ActionType,
        action_callee: str,
        action_description: str,
        should_exist=True,
        dispose_on_new_alert=False,
        force=False,
        audit_enabled=True,
    ):
        """
        should_exist = False only in mapping where the alert is not yet in elastic
        action_type = AlertActionType - the action type of the enrichment
        action_callee = the action callee of the enrichment

        Enrich the alert with extraction and mapping rules
        """
        # enrich db
        self.logger.debug(
            "enriching alert db",
            extra={"fingerprint": fingerprint, "tenant_id": self.tenant_id},
        )
        # if these enrichments are disposable, manipulate them with a timestamp
        #   so they can be disposed of later
        if dispose_on_new_alert:
            self.logger.info(
                "Enriching disposable enrichments", extra={"fingerprint": fingerprint}
            )
            # for every key, add a disposable key with the value and a timestamp
            disposable_enrichments = {}
            for key, value in enrichments.items():
                disposable_enrichments[f"disposable_{key}"] = {
                    "value": value,
                    "timestamp": datetime.datetime.utcnow().timestamp(),  # timestamp for disposal [for future use]
                }
            enrichments.update(disposable_enrichments)

        enrich_alert_db(
            self.tenant_id,
            fingerprint,
            enrichments,
            action_callee=action_callee,
            action_type=action_type,
            action_description=action_description,
            session=self.db_session,
            force=force,
            audit_enabled=audit_enabled,
        )

        self.logger.debug(
            "alert enriched in db, enriching elastic",
            extra={"fingerprint": fingerprint},
        )
        # enrich elastic only if should exist, since
        #   in elastic the alertdto is being kept which is alert + enrichments
        # so for example, in mapping, the enrichment happens before the alert is indexed in elastic
        #
        if should_exist:
            self.elastic_client.enrich_alert(
                alert_fingerprint=fingerprint,
                alert_enrichments=enrichments,
            )
        self.logger.debug(
            "alert enriched in elastic", extra={"fingerprint": fingerprint}
        )

    def get_total_enrichment_events(self, rule_id: int):
        query = select(func.count(EnrichmentEvent.id)).where(
            EnrichmentEvent.rule_id == rule_id,
            EnrichmentEvent.tenant_id == self.tenant_id,
        )
        return self.db_session.exec(query).one()

    def get_enrichment_event(self, enrichment_event_id: UUID) -> EnrichmentEvent:
        query = select(EnrichmentEvent).where(
            EnrichmentEvent.id == enrichment_event_id,
            EnrichmentEvent.tenant_id == self.tenant_id,
        )
        enrichment_event = self.db_session.exec(query).one()
        if not enrichment_event:
            raise HTTPException(status_code=404, detail="Enrichment event not found")
        return enrichment_event

    def get_enrichment_events(self, rule_id: int, limit: int, offset: int):
        # todo: easy to make async
        query = (
            select(EnrichmentEvent)
            .where(
                EnrichmentEvent.rule_id == rule_id,
                EnrichmentEvent.tenant_id == self.tenant_id,
            )
            .order_by(EnrichmentEvent.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.db_session.exec(query).all()

    def get_enrichment_event_logs(self, enrichment_event_id: UUID):
        query = select(EnrichmentLog).where(
            EnrichmentLog.enrichment_event_id == enrichment_event_id,
            EnrichmentLog.tenant_id == self.tenant_id,
        )
        return self.db_session.exec(query).all()

    def dispose_enrichments(self, fingerprint: str):
        """
        Dispose of enrichments from the alert
        """
        if EnrichmentsBl.ENRICHMENT_DISABLED:
            self.logger.debug("Enrichment is disabled, skipping dispose enrichments")
            return

        self.logger.debug("disposing enrichments", extra={"fingerprint": fingerprint})
        enrichments = get_enrichment_with_session(
            self.db_session, self.tenant_id, fingerprint
        )
        if not enrichments or not enrichments.enrichments:
            self.logger.debug(
                "no enrichments to dispose", extra={"fingerprint": fingerprint}
            )
            return
        # Remove all disposable enrichments
        new_enrichments = {}
        disposed = False
        for key, val in enrichments.enrichments.items():
            if key.startswith("disposable_"):
                disposed = True
                continue
            elif f"disposable_{key}" not in enrichments.enrichments:
                new_enrichments[key] = val
        # Only update the alert if there are disposable enrichments to dispose
        disposed_keys = set(enrichments.enrichments.keys()) - set(
            new_enrichments.keys()
        )
        if disposed:
            enrich_alert_db(
                self.tenant_id,
                fingerprint,
                new_enrichments,
                session=self.db_session,
                action_callee="system",
                action_type=ActionType.DISPOSE_ENRICHED_ALERT,
                action_description=f"Disposing enrichments from alert - {disposed_keys}",
                force=True,
            )
            self.elastic_client.enrich_alert(fingerprint, new_enrichments)
            self.logger.debug(
                "enrichments disposed", extra={"fingerprint": fingerprint}
            )

    def _track_enrichment_event(
        self,
        alert_id: UUID,
        status: EnrichmentStatus,
        enrichment_type: EnrichmentType,
        rule_id: int | None,
        enriched_fields: dict,
    ) -> None:
        """
        Track an enrichment event in the database
        """
        try:
            enrichment_event = EnrichmentEvent(
                tenant_id=self.tenant_id,
                status=status.value,
                enrichment_type=enrichment_type.value,
                rule_id=rule_id,
                alert_id=alert_id,
                enriched_fields=enriched_fields,
            )
            self.db_session.add(enrichment_event)
            self.db_session.flush()
            if self.__logs:
                for log in self.__logs:
                    log.enrichment_event_id = enrichment_event.id
                    self.db_session.add(log)
            self.db_session.commit()
            self.__logs = []
        except Exception:
            self.__logs = []
            self.logger.exception(
                "Failed to track enrichment event",
                extra={
                    "tenant_id": self.tenant_id,
                    "alert_id": alert_id,
                    "enrichment_type": enrichment_type.value,
                    "rule_id": rule_id,
                },
            )

    def _add_enrichment_log(
        self,
        message: str,
        level: str,
        details: dict | None = None,
    ) -> None:
        """
        Add a log entry for an enrichment event
        """
        try:
            getattr(self.logger, level)(message, extra=details)
            log_entry = EnrichmentLog(
                tenant_id=self.tenant_id,
                message=message,
            )
            self.__logs.append(log_entry)
        except Exception:
            self.logger.exception(
                "Failed to add enrichment log",
                extra={
                    "tenant_id": self.tenant_id,
                    "message": message,
                },
            )
