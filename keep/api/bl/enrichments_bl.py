import datetime
import json
import logging
import re

import celpy
import chevron
from sqlmodel import Session

from keep.api.core.config import config
from keep.api.core.db import enrich_entity as enrich_alert_db
from keep.api.core.db import (
    get_enrichment_with_session,
    get_mapping_rule_by_id,
    get_session_sync,
    get_topology_data_by_dynamic_matcher,
)
from keep.api.core.elastic import ElasticClient
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import ActionType
from keep.api.models.db.extraction import ExtractionRule
from keep.api.models.db.mapping import MappingRule


def get_nested_attribute(obj: AlertDto, attr_path: str):
    """
    Recursively get a nested attribute
    """
    # Special case for source, since it's a list
    if attr_path == "source" and obj.source is not None and len(obj.source) > 0:
        return obj.source[0]

    if "&&" in attr_path:
        attr_paths = [attr.strip() for attr in attr_path.split("&&")]
        return (
            all(get_nested_attribute(obj, attr) is not None for attr in attr_paths)
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
        if not EnrichmentsBl.ENRICHMENT_DISABLED:
            self.db_session = db or get_session_sync()
            self.elastic_client = ElasticClient(tenant_id=tenant_id)

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
        self.logger.info(
            "Running extraction rules for incoming event",
            extra={"tenant_id": self.tenant_id, "fingerprint": fingerprint},
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
            self.logger.debug("No extraction rules found for tenant")
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
                self.logger.info(
                    "Attribute value is empty, skipping extraction",
                    extra={"rule_id": rule.id},
                )
                continue

            if rule.condition is None or rule.condition == "*" or rule.condition == "":
                self.logger.info(
                    "No condition specified for the rule, enriching...",
                    extra={
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
                    self.logger.debug(
                        "Condition did not match, skipping extraction",
                        extra={"rule_id": rule.id},
                    )
                    continue
            match_result = re.search(rule.regex, attribute_value)
            if match_result:
                match_dict = match_result.groupdict()

                # handle source as a special case
                if "source" in match_dict:
                    source = match_dict.pop("source")
                    if source and isinstance(source, str):
                        event["source"] = [source]

                event.update(match_dict)
                self.logger.info(
                    "Event enriched with extraction rule",
                    extra={
                        "rule_id": rule.id,
                        "tenant_id": self.tenant_id,
                        "fingerprint": fingerprint,
                    },
                )
            else:
                self.logger.info(
                    "Regex did not match, skipping extraction",
                    extra={
                        "rule_id": rule.id,
                        "tenant_id": self.tenant_id,
                        "fingerprint": fingerprint,
                    },
                )

        return AlertDto(**event) if is_alert_dto else event

    def run_mapping_rule_by_id(
        self,
        rule_id: int,
        lst: list[dict],
        entry_key: str,
        matcher: str,
        key: str,
    ) -> list:
        """
        Read keep/functions/__init__.py.run_mapping function docstring for more information.
        """
        self.logger.info("Running mapping rule by ID", extra={"rule_id": rule_id})
        mapping_rule = get_mapping_rule_by_id(self.tenant_id, rule_id)
        if not mapping_rule:
            self.logger.warning("Mapping rule not found", extra={"rule_id": rule_id})
            return []

        result = []
        for entry in lst:
            entry_key_value = entry.get(entry_key)
            if entry_key_value is None:
                self.logger.warning("Entry key not found", extra={"entry": entry})
                continue
            for row in mapping_rule.rows:
                if row.get(matcher) == entry_key_value:
                    result.append(row.get(key))
                    break
        self.logger.info(
            "Mapping rule executed", extra={"rule_id": rule_id, "result": result}
        )
        return result

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

        self.logger.info(
            "Running mapping rules for incoming alert",
            extra={"fingerprint": alert.fingerprint, "tenant_id": self.tenant_id},
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
            self.logger.debug("No mapping rules found for tenant")
            return alert

        for rule in rules:
            if self._check_alert_matches_rule(alert, rule):
                self.logger.info(
                    "Alert enriched by mapping rule",
                    extra={"rule_id": rule.id, "alert_fingerprint": alert.fingerprint},
                )
            else:
                self.logger.debug(
                    "Alert not enriched by mapping rule",
                    extra={"rule_id": rule.id, "alert_fingerprint": alert.fingerprint},
                )

        return alert

    def _check_alert_matches_rule(self, alert: AlertDto, rule: MappingRule) -> bool:
        """
        Check if the alert matches the conditions specified in the mapping rule.
        If a match is found, enrich the alert and log the enrichment.

        Args:
        - alert (AlertDto): The incoming alert to be processed.
        - rule (MappingRule): The mapping rule to be checked against.

        Returns:
        - bool: True if alert matches the rule, False otherwise.
        """
        self.logger.debug(
            "Checking alert against mapping rule",
            extra={"fingerprint": alert.fingerprint, "rule_id": rule.id},
        )

        # Check if the alert has any of the attributes defined in matchers
        if not any(
            get_nested_attribute(alert, matcher) is not None
            for matcher in rule.matchers
        ):
            self.logger.debug(
                "Alert does not match any of the conditions for the rule",
                extra={
                    "fingerprint": alert.fingerprint,
                    "rule_id": rule.id,
                    "matchers": rule.matchers,
                    "alert": str(alert),
                },
            )
            return False

        self.logger.info(
            "Alert matched a mapping rule, enriching...",
            extra={"fingerprint": alert.fingerprint, "rule_id": rule.id},
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
                self.logger.debug(
                    "No topology service found to match on",
                    extra={"matcher_value": matcher_value},
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
                                if key in matcher.replace(" ", "").split("&&"):
                                    is_matcher = True
                                    break
                            if not is_matcher:
                                # If the key has . (dot) in it, it'll be added as is while it needs to be nested.
                                # @tb: fix when somebody will be complaining about this.
                                enrichments[key] = value
                    break

        if enrichments:
            # Enrich the alert with the matched data from the row
            for key, value in enrichments.items():
                # It's not relevant to enrich if the value if empty
                if value is not None:
                    setattr(alert, key, value)

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

            self.logger.info(
                "Alert enriched",
                extra={"fingerprint": alert.fingerprint, "rule_id": rule.id},
            )

            return True  # Exit on first successful enrichment (assuming single match)

        self.logger.info(
            "Alert was not enriched by mapping rule",
            extra={"rule_id": rule.id, "alert_fingerprint": alert.fingerprint},
        )
        return False

    @staticmethod
    def _is_match(value, pattern):
        if value is None or pattern is None:
            return False
        return re.search(pattern, value) is not None

    def _check_matcher(self, alert: AlertDto, row: dict, matcher: str) -> bool:
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
            if "&&" in matcher:
                # Split by "&&" for AND condition
                conditions = matcher.split("&&")
                return all(
                    self._is_match(
                        get_nested_attribute(alert, attribute.strip()),
                        row.get(attribute.strip()),
                    )
                    or get_nested_attribute(alert, attribute.strip())
                    == row.get(attribute.strip())
                    or row.get(attribute.strip()) == "*"  # Wildcard match
                    for attribute in conditions
                )
            else:
                # Single condition check
                return (
                    self._is_match(
                        get_nested_attribute(alert, matcher), row.get(matcher)
                    )
                    or get_nested_attribute(alert, matcher) == row.get(matcher)
                    or row.get(matcher) == "*"  # Wildcard match
                )
        except TypeError:
            self.logger.exception("Error while checking matcher")
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
