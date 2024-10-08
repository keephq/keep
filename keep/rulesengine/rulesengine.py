import json
import logging
from typing import Optional

import celpy
import celpy.c7nlib
import celpy.celparser
import celpy.celtypes
import celpy.evaluation
from sqlmodel import Session

from keep.api.consts import STATIC_PRESETS
from keep.api.core.db import assign_alert_to_incident, get_incident_for_grouping_rule, is_all_incident_alerts_resolved, \
    is_first_incident_alert_resolved, is_last_incident_alert_resolved
from keep.api.core.db import get_rules as get_rules_db
from keep.api.models.alert import AlertDto, AlertSeverity, IncidentDto, IncidentStatus
from keep.api.models.db.rule import ResolveOn
from keep.api.utils.cel_utils import preprocess_cel_expression

# Shahar: this is performance enhancment https://github.com/cloud-custodian/cel-python/issues/68


celpy.evaluation.Referent.__repr__ = lambda self: ""
celpy.evaluation.NameContainer.__repr__ = lambda self: ""
celpy.Activation.__repr__ = lambda self: ""
celpy.Activation.__str__ = lambda self: ""
celpy.celtypes.MapType.__repr__ = lambda self: ""
celpy.celtypes.DoubleType.__repr__ = lambda self: ""
celpy.celtypes.BytesType.__repr__ = lambda self: ""
celpy.celtypes.IntType.__repr__ = lambda self: ""
celpy.celtypes.UintType.__repr__ = lambda self: ""
celpy.celtypes.ListType.__repr__ = lambda self: ""
celpy.celtypes.StringType.__repr__ = lambda self: ""
celpy.celtypes.TimestampType.__repr__ = lambda self: ""
celpy.c7nlib.C7NContext.__repr__ = lambda self: ""
celpy.celparser.Tree.__repr__ = lambda self: ""


class RulesEngine:
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(__name__)
        self.env = celpy.Environment()

    def run_rules(self, events: list[AlertDto], session: Optional[Session] = None) -> list[IncidentDto]:
        self.logger.info("Running rules")
        rules = get_rules_db(tenant_id=self.tenant_id)

        incidents_dto = {}
        for rule in rules:
            self.logger.info(f"Evaluating rule {rule.name}")
            for event in events:
                self.logger.info(
                    f"Checking if rule {rule.name} apply to event {event.id}"
                )
                try:
                    rule_result = self._check_if_rule_apply(rule, event)
                except Exception:
                    self.logger.exception(
                        f"Failed to evaluate rule {rule.name} on event {event.id}"
                    )
                    continue
                if rule_result:
                    self.logger.info(
                        f"Rule {rule.name} on event {event.id} is relevant"
                    )

                    rule_fingerprint = self._calc_rule_fingerprint(event, rule)

                    incident = get_incident_for_grouping_rule(
                        self.tenant_id, rule, rule.timeframe, rule_fingerprint,
                        session=session
                    )

                    incident = assign_alert_to_incident(
                        alert_id=event.event_id,
                        incident=incident,
                        tenant_id=self.tenant_id,
                        session=session
                    )

                    should_resolve = False

                    if rule.resolve_on == ResolveOn.ALL.value and is_all_incident_alerts_resolved(incident, session=session):
                        should_resolve = True

                    elif rule.resolve_on == ResolveOn.FIRST.value and is_first_incident_alert_resolved(incident, session=session):
                        should_resolve = True

                    if rule.resolve_on == ResolveOn.LAST.value and is_last_incident_alert_resolved(incident, session=session):
                        should_resolve = True

                    if should_resolve:
                        incident.status = IncidentStatus.RESOLVED.value
                        session.add(incident)
                        session.commit()

                    incidents_dto[incident.id] = IncidentDto.from_db_incident(incident)
                else:
                    self.logger.info(
                        f"Rule {rule.name} on event {event.id} is not relevant"
                    )
        self.logger.info("Rules ran successfully")
        # if we don't have any updated groups, we don't need to create any alerts
        if not incidents_dto:
            return []

        self.logger.info(f"Rules ran, {len(incidents_dto)} incidents created")

        return list(incidents_dto.values())

    def _extract_subrules(self, expression):
        # CEL rules looks like '(source == "sentry") && (source == "grafana" && severity == "critical")'
        # and we need to extract the subrules
        sub_rules = expression.split(") && (")
        if len(sub_rules) == 1:
            return sub_rules
        # the first and the last rules will have a ( or ) at the beginning or the end
        # e.g. for the example of:
        #           (source == "sentry") && (source == "grafana" && severity == "critical")
        # than sub_rules[0] will be (source == "sentry" and sub_rules[-1] will be source == "grafana" && severity == "critical")
        # so we need to remove the first and last character
        sub_rules[0] = sub_rules[0][1:]
        sub_rules[-1] = sub_rules[-1][:-1]
        return sub_rules

    # TODO: a lot of unit tests to write here
    def _check_if_rule_apply(self, rule, event: AlertDto):
        sub_rules = self._extract_subrules(rule.definition_cel)
        payload = event.dict()
        # workaround since source is a list
        # todo: fix this in the future
        payload["source"] = payload["source"][0]

        # what we do here is to compile the CEL rule and evaluate it
        #   https://github.com/cloud-custodian/cel-python
        #   https://github.com/google/cel-spec
        for sub_rule in sub_rules:
            ast = self.env.compile(sub_rule)
            prgm = self.env.program(ast)
            activation = celpy.json_to_cel(json.loads(json.dumps(payload, default=str)))
            try:
                r = prgm.evaluate(activation)
            except celpy.evaluation.CELEvalError as e:
                # this is ok, it means that the subrule is not relevant for this event
                if "no such member" in str(e):
                    return False
                # unknown
                raise
            if r:
                return True
        # no subrules matched
        return False

    def _calc_rule_fingerprint(self, event: AlertDto, rule):
        # extract all the grouping criteria from the event
        # e.g. if the grouping criteria is ["event.labels.queue", "event.labels.cluster"]
        #     and the event is:
        #    {
        #      "labels": {
        #        "queue": "queue1",
        #        "cluster": "cluster1",
        #        "foo": "bar"
        #      }
        #    }
        # than the rule_fingerprint will be "queue1,cluster1"

        # note: rule_fingerprint is not a unique id, since different rules can lead to the same rule_fingerprint
        #       hence, the actual fingerprint is composed of the rule_fingerprint and the incident id
        event_payload = event.dict()
        grouping_criteria = rule.grouping_criteria or []
        rule_fingerprint = []
        for criteria in grouping_criteria:
            # we need to extract the value from the event
            # e.g. if the criteria is "event.labels.queue"
            # than we need to extract the value of event["labels"]["queue"]
            criteria_parts = criteria.split(".")
            value = event_payload
            for part in criteria_parts:
                value = value.get(part)
            if isinstance(value, list):
                value = ",".join(value)
            rule_fingerprint.append(value)
        # if, for example, the event should have labels.X but it doesn't,
        # than we will have None in the rule_fingerprint
        if not rule_fingerprint:
            self.logger.warning(
                f"Failed to calculate rule fingerprint for event {event.id} and rule {rule.name}"
            )
            return "none"
        # if any of the values is None, we will return "none"
        if any([fingerprint is None for fingerprint in rule_fingerprint]):
            self.logger.warning(
                f"Failed to fetch the appropriate labels from the event {event.id} and rule {rule.name}"
            )
            return "none"
        return ",".join(rule_fingerprint)

    def get_alerts_activation(self, alerts: list[AlertDto]):
        activations = []
        for alert in alerts:
            payload = alert.dict()
            # TODO: workaround since source is a list
            #       should be fixed in the future
            payload["source"] = ",".join(payload["source"])
            # payload severity could be the severity itself or the order of the severity, cast it to the order
            if isinstance(payload["severity"], str):
                payload["severity"] = AlertSeverity(payload["severity"].lower()).order
            activation = celpy.json_to_cel(json.loads(json.dumps(payload, default=str)))
            activations.append(activation)
        return activations

    def filter_alerts(
        self, alerts: list[AlertDto], cel: str, alerts_activation: list = None
    ):
        """This function filters alerts according to a CEL

        Args:
            alerts (list[AlertDto]): list of alerts
            cel (str): CEL expression

        Returns:
            list[AlertDto]: list of alerts that are related to the cel
        """
        logger = logging.getLogger(__name__)

        # tb: temp hack because this function is super slow
        if cel == STATIC_PRESETS.get("feed", {}).options[0].get("value"):
            return [
                alert
                for alert in alerts
                if (alert.deleted == False and alert.dismissed == False)
            ]
        # if the cel is empty, return all the alerts
        if not cel:
            logger.debug("No CEL expression provided")
            return alerts
        # preprocess the cel expression
        cel = preprocess_cel_expression(cel)
        ast = self.env.compile(cel)
        prgm = self.env.program(ast)
        filtered_alerts = []

        for i, alert in enumerate(alerts):
            if alerts_activation:
                activation = alerts_activation[i]
            else:
                activation = self.get_alerts_activation([alert])[0]
            try:
                r = prgm.evaluate(activation)
            except celpy.evaluation.CELEvalError as e:
                # this is ok, it means that the subrule is not relevant for this event
                if "no such member" in str(e):
                    continue
                # unknown
                elif "no such overload" in str(e):
                    logger.debug(
                        f"Type mismtach between operator and operand in the CEL expression {cel} for alert {alert.id}"
                    )
                    continue
                elif "found no matching overload" in str(e):
                    logger.debug(
                        f"Type mismtach between operator and operand in the CEL expression {cel} for alert {alert.id}"
                    )
                    continue
                logger.warning(
                    f"Failed to evaluate the CEL expression {cel} for alert {alert.id} - {e}"
                )
                continue
            except Exception:
                logger.exception(
                    f"Failed to evaluate the CEL expression {cel} for alert {alert.id}"
                )
                continue
            if r:
                filtered_alerts.append(alert)

        return filtered_alerts
