"""
Enrichment business logic (single-file version).

Fixes:
- Session ownership & lifecycle management (no leaks)
- No nested commits in helper methods
- Rollback on failure
- Commit only when we own the session
- Safe boolean filtering (SQLAlchemy .is_(False))
- Fixed get_nested_attribute list behavior
- Safe alert.event handling
- Guard elastic calls when disabled
- Restore session state when modified (expire_on_commit)
"""

from __future__ import annotations

import datetime
import html
import json
import logging
import re
import uuid
from copy import deepcopy
from typing import Any, Optional
from uuid import UUID

import celpy
import chevron
import json5
from elasticsearch import NotFoundError
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import NoResultFound
from sqlalchemy_utils import UUIDType
from sqlmodel import Session, select

from keep.api.core.config import config
from keep.api.core.db import batch_enrich
from keep.api.core.db import enrich_entity as enrich_alert_db
from keep.api.core.db import (
    get_alert_by_event_id,
    get_enrichment_with_session,
    get_extraction_rule_by_id,
    get_incidents_by_alert_fingerprint,
    get_last_alert_by_fingerprint,
    get_mapping_rule_by_id,
    get_session_sync,
    get_topology_data_by_dynamic_matcher,
    is_all_alerts_resolved,
)
from keep.api.core.elastic import ElasticClient
from keep.api.models.action_type import ActionType
from keep.api.models.alert import AlertDto
from keep.api.models.db.alert import Alert
from keep.api.models.db.enrichment_event import (
    EnrichmentEvent,
    EnrichmentLog,
    EnrichmentStatus,
    EnrichmentType,
)
from keep.api.models.db.extraction import ExtractionRule
from keep.api.models.db.incident import IncidentStatus
from keep.api.models.db.mapping import MappingRule
from keep.api.models.db.rule import ResolveOn
from keep.identitymanager.authenticatedentity import AuthenticatedEntity


def is_valid_uuid(uuid_str: Any) -> bool:
    if isinstance(uuid_str, UUID):
        return True
    try:
        uuid.UUID(str(uuid_str))
        return True
    except (ValueError, TypeError):
        return False


def get_nested_attribute(obj: AlertDto | dict, attr_path: str | list[str]):
    """
    Get nested attribute value(s).
    - If attr_path is a string -> returns value or None
    - If attr_path is a list -> returns list of values, or None if any missing
    Special handling for 'source' because it's a list and we typically want first element.
    """

    if isinstance(attr_path, list):
        values = []
        for p in attr_path:
            v = get_nested_attribute(obj, p)
            if v is None:
                return None
            values.append(v)
        return values

    if attr_path == "source":
        src = obj.get("source") if isinstance(obj, dict) else getattr(obj, "source", None)
        if isinstance(src, list) and src:
            return src[0]
        return None

    parts = attr_path.split(".")
    cur: Any = obj
    for part in parts:
        # @@ is placeholder for '.' inside attribute names
        if part and "@@" in part:
            part = part.replace("@@", ".")
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


class EnrichmentsBl:
    ENRICHMENT_DISABLED = config("KEEP_ENRICHMENT_DISABLED", default="false", cast=bool)

    def __init__(self, tenant_id: str, db: Session | None = None):
        self.logger = logging.getLogger(__name__)
        self.tenant_id = tenant_id

        self.__logs: list[EnrichmentLog] = []
        self.enrichment_event_id: UUID | None = None

        self._owns_session = False
        self.db_session: Session | None = None
        self.elastic_client: ElasticClient | None = None

        if not EnrichmentsBl.ENRICHMENT_DISABLED:
            self._owns_session = db is None
            self.db_session = db or get_session_sync()
            self.elastic_client = ElasticClient(tenant_id=tenant_id)

    # -------- lifecycle --------

    def close(self) -> None:
        if self._owns_session and self.db_session is not None:
            try:
                self.db_session.close()
            except Exception:
                self.logger.exception("Failed closing owned session")

    def __enter__(self) -> "EnrichmentsBl":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # If we own the session, keep it clean.
        if self.db_session is not None and self._owns_session:
            if exc_type is not None:
                try:
                    self.db_session.rollback()
                except Exception:
                    self.logger.exception("Rollback failed on exit")
        self.close()

    def __del__(self):
        # Best effort. Prefer using `with EnrichmentsBl(...) as bl:`
        try:
            self.close()
        except Exception:
            pass

    # -------- small helpers --------

    def _require_session(self) -> Session:
        if EnrichmentsBl.ENRICHMENT_DISABLED or self.db_session is None:
            raise RuntimeError("Enrichment DB session is not initialized (disabled or missing).")
        return self.db_session

    def _commit_if_owned(self) -> None:
        if self.db_session is not None and self._owns_session:
            self.db_session.commit()

    def _rollback_if_owned(self) -> None:
        if self.db_session is not None and self._owns_session:
            self.db_session.rollback()

    # -------- public entrypoints --------

    def run_mapping_rule_by_id(self, rule_id: int, alert_id: UUID) -> AlertDto:
        session = self._require_session()
        rule = get_mapping_rule_by_id(self.tenant_id, rule_id, session=session)
        if not rule:
            raise HTTPException(status_code=404, detail="Mapping rule not found")

        alert = get_alert_by_event_id(self.tenant_id, str(alert_id), session=session)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")

        # Ensure we have AlertDto
        alert_dto = AlertDto(**alert.event) if isinstance(alert, Alert) else alert
        self.check_if_match_and_enrich(alert_dto, rule)

        # Commit only if we own the session
        self._commit_if_owned()
        return alert_dto

    def run_extraction_rule_by_id(self, rule_id: int, alert: Alert) -> AlertDto:
        session = self._require_session()
        rule = get_extraction_rule_by_id(self.tenant_id, rule_id, session=session)
        if not rule:
            raise HTTPException(status_code=404, detail="Extraction rule not found")

        if not isinstance(alert.event, dict):
            raise HTTPException(status_code=400, detail="Alert event payload is invalid")

        # track enrichment event
        alert.event["event_id"] = alert.id
        result = self.run_extraction_rules(alert.event, pre=False, rules=[rule])

        # Commit only if we own the session
        self._commit_if_owned()

        if isinstance(result, AlertDto):
            return result
        return AlertDto(**result)

    def run_extraction_rules(
        self,
        event: AlertDto | dict,
        pre: bool = False,
        rules: list[ExtractionRule] | None = None,
    ) -> AlertDto | dict:
        """
        Run extraction rules. Returns the same type that was passed in (AlertDto in -> AlertDto out).
        """
        if EnrichmentsBl.ENRICHMENT_DISABLED:
            self.logger.debug("Enrichment is disabled, skipping extraction rules")
            return event

        session = self._require_session()

        input_is_dto = isinstance(event, AlertDto)
        event_dict: dict = event.dict() if input_is_dto else deepcopy(event)

        fingerprint = event_dict.get("fingerprint")
        event_id = event_dict.get("event_id") or event_dict.get("id")

        self._add_enrichment_log(
            "Running extraction rules for incoming event",
            "info",
            {
                "tenant_id": self.tenant_id,
                "fingerprint": fingerprint,
                "event_id": str(event_id) if event_id else None,
                "pre": pre,
            },
        )

        rules = rules or (
            session.query(ExtractionRule)
            .filter(ExtractionRule.tenant_id == self.tenant_id)
            .filter(ExtractionRule.disabled.is_(False))
            .filter(ExtractionRule.pre == pre)
            .order_by(ExtractionRule.priority.desc())
            .all()
        )

        if not rules:
            self._add_enrichment_log(
                f"No extraction rules found (pre: {pre})",
                "debug",
                {
                    "tenant_id": self.tenant_id,
                    "fingerprint": fingerprint,
                    "event_id": str(event_id) if event_id else None,
                    "pre": pre,
                },
            )
            self._track_enrichment_event(
                event_id, EnrichmentStatus.SKIPPED, EnrichmentType.EXTRACTION, 0, {}
            )
            self._commit_if_owned()
            return AlertDto(**event_dict) if input_is_dto else event_dict

        try:
            for rule in rules:
                attribute = rule.attribute
                if not (attribute.startswith("{{") and attribute.endswith("}}")):
                    attribute = f"{{{{ {attribute} }}}}"

                attribute_value = chevron.render(attribute, event_dict)
                attribute_value = html.unescape(attribute_value)

                if not attribute_value:
                    self._add_enrichment_log(
                        f"Attribute ({rule.attribute}) value is empty, skipping extraction",
                        "info",
                        {"rule_id": rule.id},
                    )
                    self._track_enrichment_event(
                        event_id,
                        EnrichmentStatus.SKIPPED,
                        EnrichmentType.EXTRACTION,
                        rule.id,
                        {},
                    )
                    continue

                # condition check
                if rule.condition not in (None, "", "*"):
                    env = celpy.Environment()
                    ast = env.compile(rule.condition)
                    prgm = env.program(ast)
                    activation = celpy.json_to_cel(event_dict)
                    relevant = prgm.evaluate(activation)
                    if not relevant:
                        self._add_enrichment_log(
                            f"Condition did not match, skipping extraction for rule {rule.name}",
                            "debug",
                            {"rule_id": rule.id},
                        )
                        self._track_enrichment_event(
                            event_id,
                            EnrichmentStatus.SKIPPED,
                            EnrichmentType.EXTRACTION,
                            rule.id,
                            {},
                        )
                        continue

                match_result = re.search(rule.regex, attribute_value)
                if match_result:
                    match_dict = match_result.groupdict()
                    match_dict.pop("source", None)  # never override source
                    event_dict.update(match_dict)

                    self.enrich_entity(
                        fingerprint,
                        match_dict,
                        action_type=ActionType.EXTRACTION_RULE_ENRICH,
                        action_callee="system",
                        action_description=f"Alert enriched with extraction from rule `{rule.name}`",
                        should_exist=False,
                    )
                    self._add_enrichment_log(
                        "Event enriched with extraction rule",
                        "info",
                        {"rule_id": rule.id, "tenant_id": self.tenant_id, "fingerprint": fingerprint},
                    )
                    self._track_enrichment_event(
                        event_id,
                        EnrichmentStatus.SUCCESS,
                        EnrichmentType.EXTRACTION,
                        rule.id,
                        match_dict,
                    )
                else:
                    self._add_enrichment_log(
                        "Regex did not match, skipping extraction",
                        "info",
                        {"rule_id": rule.id, "tenant_id": self.tenant_id, "fingerprint": fingerprint},
                    )
                    self._track_enrichment_event(
                        event_id,
                        EnrichmentStatus.SKIPPED,
                        EnrichmentType.EXTRACTION,
                        rule.id,
                        {},
                    )

            self._commit_if_owned()
            return AlertDto(**event_dict) if input_is_dto else event_dict

        except Exception:
            self._rollback_if_owned()
            self.logger.exception("Extraction rules processing failed", extra={"tenant_id": self.tenant_id})
            raise

    def run_mapping_rules(self, alert: AlertDto) -> AlertDto:
        """
        Run mapping rules for the alert.
        """
        if EnrichmentsBl.ENRICHMENT_DISABLED:
            self.logger.debug("Enrichment is disabled, skipping mapping rules")
            return alert

        session = self._require_session()

        self._add_enrichment_log(
            "Running mapping rules for incoming alert",
            "info",
            {"fingerprint": alert.fingerprint, "tenant_id": self.tenant_id},
        )

        rules: list[MappingRule] = (
            session.query(MappingRule)
            .filter(MappingRule.tenant_id == self.tenant_id)
            .filter(MappingRule.disabled.is_(False))
            .order_by(MappingRule.priority.desc())
            .all()
        )

        if not rules:
            self._add_enrichment_log(
                "No mapping rules found for tenant",
                "debug",
                {"fingerprint": alert.fingerprint, "tenant_id": self.tenant_id},
            )
            return alert

        try:
            for rule in rules:
                self.check_if_match_and_enrich(alert, rule)

            self._commit_if_owned()
            return alert

        except Exception:
            self._rollback_if_owned()
            self.logger.exception("Mapping rules processing failed", extra={"tenant_id": self.tenant_id})
            raise

    # -------- mapping logic --------

    def check_if_match_and_enrich(self, alert: AlertDto, rule: MappingRule) -> bool:
        """
        Check whether an alert matches a mapping rule, and enrich if matched.
        """
        self._add_enrichment_log(
            "Checking alert against mapping rule",
            "debug",
            {"fingerprint": alert.fingerprint, "rule_id": rule.id},
        )

        match = False
        for matcher in rule.matchers:
            if matcher and get_nested_attribute(alert, matcher) is not None:
                match = True
                break

        if not match:
            self._track_enrichment_event(
                alert.id, EnrichmentStatus.SKIPPED, EnrichmentType.MAPPING, rule.id, {}
            )
            return False

        enrichments: dict[str, Any] = {}

        if rule.type == "topology":
            matcher_value = {}
            for matcher in rule.matchers:
                matcher_value[matcher[0]] = get_nested_attribute(alert, matcher[0])

            topology_service = get_topology_data_by_dynamic_matcher(self.tenant_id, matcher_value)
            if topology_service:
                enrichments = topology_service.dict(exclude_none=True)
                if not topology_service.repository and topology_service.applications:
                    for application in topology_service.applications:
                        if application.repository:
                            enrichments["repository"] = application.repository
                enrichments.pop("tenant_id", None)
                enrichments.pop("id", None)

        elif rule.type == "csv":
            if not rule.is_multi_level:
                for row in rule.rows:
                    if any(self._check_matcher(alert, row, matcher) for matcher in rule.matchers):
                        for key, value in row.items():
                            if value is None:
                                continue
                            is_matcher = any(key in m for m in rule.matchers)
                            if not is_matcher:
                                if isinstance(value, str):
                                    value = value.strip()
                                enrichments[key.strip()] = value
                        break
            else:
                key = rule.matchers[0][0]
                matcher_values = get_nested_attribute(alert, key)
                if matcher_values:
                    if isinstance(matcher_values, str):
                        matcher_values = json5.loads(matcher_values)

                    for matcher in matcher_values:
                        if rule.prefix_to_remove:
                            matcher = matcher.replace(rule.prefix_to_remove, "")

                        for row in rule.rows:
                            if self._check_explicit_match(row, key, matcher):
                                if rule.new_property_name not in enrichments:
                                    enrichments[rule.new_property_name] = {}
                                if matcher not in enrichments[rule.new_property_name]:
                                    enrichments[rule.new_property_name][matcher] = {}

                                for ek, ev in row.items():
                                    if ev is not None:
                                        enrichments[rule.new_property_name][matcher][ek.strip()] = str(ev).strip()
                                break

        if enrichments:
            for key, value in enrichments.items():
                if value is None:
                    continue
                if isinstance(value, str):
                    value = value.strip()
                setattr(alert, key.strip(), value)

            self.enrich_entity(
                alert.fingerprint,
                enrichments,
                action_type=ActionType.MAPPING_RULE_ENRICH,
                action_callee="system",
                action_description=f"Alert enriched with mapping from rule `{rule.name}`",
                should_exist=False,
            )

            self._track_enrichment_event(
                alert.id, EnrichmentStatus.SUCCESS, EnrichmentType.MAPPING, rule.id, enrichments
            )
            return True

        self._track_enrichment_event(
            alert.id, EnrichmentStatus.FAILURE, EnrichmentType.MAPPING, rule.id, {}
        )
        return False

    @staticmethod
    def _is_match(value: Any, pattern: Any) -> bool:
        if value is None or pattern is None:
            return False
        try:
            return re.search(str(pattern), str(value)) is not None
        except re.error:
            return False

    def _check_explicit_match(self, row: dict, matcher: str, explicit_value: str) -> bool:
        return str(row.get(matcher.strip(), "")).strip() == str(explicit_value).strip()

    def _check_matcher(self, alert: AlertDto, row: dict, matcher: list) -> bool:
        try:
            return all(
                self._is_match(get_nested_attribute(alert, attribute.strip()), row.get(attribute.strip()))
                or get_nested_attribute(alert, attribute.strip()) == row.get(attribute.strip())
                or row.get(attribute.strip()) == "*"
                for attribute in matcher
            )
        except TypeError:
            self._add_enrichment_log(
                "Error while checking matcher",
                "error",
                {"fingerprint": alert.fingerprint, "matcher": matcher},
            )
            return False

    # -------- metadata helpers --------

    @staticmethod
    def get_enrichment_metadata(
        enrichments: dict, authenticated_entity: AuthenticatedEntity
    ) -> tuple[ActionType, str, bool, bool]:
        should_run_workflow = False
        should_check_incidents_resolution = False
        action_type = ActionType.GENERIC_ENRICH
        action_description = f"Alert enriched by {authenticated_entity.email} - {enrichments}"

        if "status" in enrichments and authenticated_entity.api_key_name is None:
            action_type = ActionType.MANUAL_RESOLVE if enrichments["status"] == "resolved" else ActionType.MANUAL_STATUS_CHANGE
            action_description = f"Alert status was changed to {enrichments['status']} by {authenticated_entity.email}"
            should_run_workflow = True
            if enrichments["status"] == "resolved":
                should_check_incidents_resolution = True

        elif "status" in enrichments and authenticated_entity.api_key_name:
            action_type = ActionType.API_AUTOMATIC_RESOLVE if enrichments["status"] == "resolved" else ActionType.API_STATUS_CHANGE
            action_description = f"Alert status was changed to {enrichments['status']} by API `{authenticated_entity.api_key_name}`"
            should_run_workflow = True
            if enrichments["status"] == "resolved":
                should_check_incidents_resolution = True

        elif "note" in enrichments and enrichments["note"]:
            action_type = ActionType.COMMENT
            action_description = f"Comment added by {authenticated_entity.email} - {enrichments['note']}"

        elif "ticket_url" in enrichments:
            action_type = ActionType.TICKET_ASSIGNED
            action_description = f"Ticket assigned by {authenticated_entity.email} - {enrichments['ticket_url']}"

        return action_type, action_description, should_run_workflow, should_check_incidents_resolution

    # -------- enrichment persistence --------

    def batch_enrich(
        self,
        fingerprints: list[str],
        enrichments: dict,
        action_type: ActionType,
        action_callee: str,
        action_description: str,
        dispose_on_new_alert: bool = False,
        audit_enabled: bool = True,
    ):
        session = self._require_session()
        self.logger.debug("enriching multiple fingerprints", extra={"tenant_id": self.tenant_id})

        if dispose_on_new_alert:
            disposable_enrichments = {}
            for key, value in enrichments.items():
                disposable_enrichments[f"disposable_{key}"] = {
                    "value": value,
                    "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).timestamp(),
                }
            enrichments.update(disposable_enrichments)

        batch_enrich(
            self.tenant_id,
            fingerprints,
            enrichments,
            action_type,
            action_callee,
            action_description,
            audit_enabled=audit_enabled,
            session=session,
        )

        self._commit_if_owned()

    def disposable_enrich_entity(
        self,
        fingerprint: str,
        enrichments: dict,
        action_type: ActionType,
        action_callee: str,
        action_description: str,
        should_exist: bool = True,
        force: bool = False,
        audit_enabled: bool = True,
    ):
        session = self._require_session()

        common_kwargs = {
            "enrichments": enrichments,
            "action_type": action_type,
            "action_callee": action_callee,
            "action_description": action_description,
            "should_exist": should_exist,
            "force": force,
        }

        self.enrich_entity(
            fingerprint=fingerprint,
            dispose_on_new_alert=True,
            audit_enabled=audit_enabled,
            **common_kwargs,
        )

        last_alert = get_last_alert_by_fingerprint(self.tenant_id, fingerprint, session=session)
        alert_id = UUIDType(binary=False).process_bind_param(last_alert.alert_id, session.bind.dialect)

        common_kwargs["should_exist"] = False
        self.enrich_entity(fingerprint=alert_id, audit_enabled=False, **common_kwargs)

        self._commit_if_owned()

    def enrich_entity(
        self,
        fingerprint: str | UUID,
        enrichments: dict,
        action_type: ActionType,
        action_callee: str,
        action_description: str,
        should_exist: bool = True,
        dispose_on_new_alert: bool = False,
        force: bool = False,
        audit_enabled: bool = True,
    ):
        session = self._require_session()

        if isinstance(fingerprint, UUID):
            fingerprint = UUIDType(binary=False).process_bind_param(fingerprint, session.bind.dialect)

        if dispose_on_new_alert:
            disposable_enrichments = {}
            for key, value in enrichments.items():
                disposable_enrichments[f"disposable_{key}"] = {
                    "value": value,
                    "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).timestamp(),
                }
            enrichments.update(disposable_enrichments)

        enrich_alert_db(
            self.tenant_id,
            fingerprint,
            enrichments,
            action_callee=action_callee,
            action_type=action_type,
            action_description=action_description,
            session=session,
            force=force,
            audit_enabled=audit_enabled,
        )

        # Elastic is best-effort. DB is source of truth.
        if should_exist and self.elastic_client:
            try:
                self.elastic_client.enrich_alert(alert_fingerprint=fingerprint, alert_enrichments=enrichments)
            except NotFoundError:
                self.logger.exception(
                    "Failed to enrich alert in Elastic",
                    extra={"fingerprint": fingerprint, "tenant_id": self.tenant_id},
                )

        self._commit_if_owned()

    def get_total_enrichment_events(
        self,
        rule_id: int,
        _type: EnrichmentType = EnrichmentType.MAPPING,
    ):
        session = self._require_session()
        query = select(func.count(EnrichmentEvent.id)).where(
            EnrichmentEvent.rule_id == rule_id,
            EnrichmentEvent.tenant_id == self.tenant_id,
            EnrichmentEvent.enrichment_type == _type.value,
        )
        return session.exec(query).one()

    def get_enrichment_event(self, enrichment_event_id: UUID) -> EnrichmentEvent:
        session = self._require_session()
        query = select(EnrichmentEvent).where(
            EnrichmentEvent.id == enrichment_event_id,
            EnrichmentEvent.tenant_id == self.tenant_id,
        )
        try:
            return session.exec(query).one()
        except NoResultFound:
            raise HTTPException(status_code=404, detail="Enrichment event not found")

    def get_enrichment_events(
        self,
        rule_id: int,
        limit: int,
        offset: int,
        _type: EnrichmentType = EnrichmentType.MAPPING,
    ):
        session = self._require_session()
        query = (
            select(EnrichmentEvent)
            .where(
                EnrichmentEvent.rule_id == rule_id,
                EnrichmentEvent.tenant_id == self.tenant_id,
                EnrichmentEvent.enrichment_type == _type.value,
            )
            .order_by(EnrichmentEvent.timestamp.desc())
            .offset(offset)
            .limit(limit)
        )
        return session.exec(query).all()

    def get_enrichment_event_logs(self, enrichment_event_id: UUID):
        session = self._require_session()
        query = select(EnrichmentLog).where(
            EnrichmentLog.enrichment_event_id == enrichment_event_id,
            EnrichmentLog.tenant_id == self.tenant_id,
        )
        return session.exec(query).all()

    def dispose_enrichments(self, fingerprint: str):
        if EnrichmentsBl.ENRICHMENT_DISABLED:
            return

        session = self._require_session()

        enrichments = get_enrichment_with_session(session, self.tenant_id, fingerprint)
        if not enrichments or not enrichments.enrichments:
            return

        keys = enrichments.enrichments
        new_enrichments = {}
        disposed = False

        for key, val in keys.items():
            if key.startswith("disposable_"):
                disposed = True
                continue
            if f"disposable_{key}" in keys:
                disposed = True
                continue
            new_enrichments[key] = val

        if not disposed:
            return

        enrich_alert_db(
            self.tenant_id,
            fingerprint,
            new_enrichments,
            session=session,
            action_callee="system",
            action_type=ActionType.DISPOSE_ENRICHED_ALERT,
            action_description="Disposing enrichments from alert",
            force=True,
        )

        self._commit_if_owned()

        if self.elastic_client:
            try:
                self.elastic_client.enrich_alert(fingerprint, new_enrichments)
            except Exception:
                self.logger.exception("Failed to update elastic during dispose", extra={"fingerprint": fingerprint})

    # -------- event tracking --------

    def _track_enrichment_event(
        self,
        alert_id: UUID | None,
        status: EnrichmentStatus,
        enrichment_type: EnrichmentType,
        rule_id: int | None,
        enriched_fields: dict,
    ) -> None:
        """
        Track an enrichment event.
        IMPORTANT: does NOT commit. Only adds + flushes.
        """
        if self.db_session is None:
            self.__logs = []
            return

        if alert_id is None or not is_valid_uuid(alert_id):
            self.__logs = []
            self.logger.debug(
                "Cannot track enrichment event without a valid alert_id",
                extra={"tenant_id": self.tenant_id, "rule_id": rule_id},
            )
            return

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

            self.__logs = []
            self.enrichment_event_id = enrichment_event.id

        except Exception:
            # If this fails, rollback only if we own the session, to avoid trashing caller transactions.
            if self._owns_session:
                self.db_session.rollback()
            self.__logs = []
            self.logger.exception(
                "Failed to track enrichment event",
                extra={
                    "tenant_id": self.tenant_id,
                    "alert_id": str(alert_id),
                    "enrichment_type": enrichment_type.value,
                    "rule_id": rule_id,
                },
            )

    def _add_enrichment_log(self, message: str, level: str, details: dict | None = None) -> None:
        try:
            getattr(self.logger, level)(message, extra=details)
            self.__logs.append(EnrichmentLog(tenant_id=self.tenant_id, message=message))
        except Exception:
            self.logger.exception("Failed to add enrichment log", extra={"tenant_id": self.tenant_id, "message": message})

    # -------- incident resolution --------

    def check_incident_resolution(self, alert: Alert | AlertDto):
        if EnrichmentsBl.ENRICHMENT_DISABLED:
            return

        session = self._require_session()

        incidents = get_incidents_by_alert_fingerprint(self.tenant_id, alert.fingerprint, session)

        original_expire = session.expire_on_commit
        try:
            session.expire_on_commit = False
            changed = False

            for incident in incidents:
                if incident.resolve_on == ResolveOn.ALL.value and is_all_alerts_resolved(incident=incident, session=session):
                    if incident.status != IncidentStatus.RESOLVED.value:
                        incident.status = IncidentStatus.RESOLVED.value
                        session.add(incident)
                        changed = True

            if changed:
                self._commit_if_owned()

        except Exception:
            self._rollback_if_owned()
            self.logger.exception("Failed incident resolution check", extra={"tenant_id": self.tenant_id})
            raise
        finally:
            session.expire_on_commit = original_expire