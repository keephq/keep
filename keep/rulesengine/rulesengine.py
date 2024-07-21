import itertools
import json
import logging
import re

import celpy
import chevron

from keep.api.consts import STATIC_PRESETS
from keep.api.core.db import assign_alert_to_group as assign_alert_to_group_db
from keep.api.core.db import create_alert as create_alert_db
from keep.api.core.db import get_rules as get_rules_db
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.api.models.group import GroupDto


class RulesEngine:
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(__name__)

    def _calc_max_severity(self, alerts):
        if not alerts:
            # should not happen
            self.logger.info(
                "Could not calculate max severity from empty list - fallbacking to info"
            )
            return str(AlertSeverity.INFO)

        alerts_by_fingerprint = {}
        for alert in alerts:
            if alert.fingerprint not in alerts_by_fingerprint:
                alerts_by_fingerprint[alert.fingerprint] = [alert]
            else:
                alerts_by_fingerprint[alert.fingerprint].append(alert)

        # now take the latest (by timestamp) for each fingerprint:
        alerts = [
            max(alerts, key=lambda alert: alert.event["lastReceived"])
            for alerts in alerts_by_fingerprint.values()
        ]
        # if all alerts are with the same status, just use it
        severities = [AlertSeverity(alert.event["severity"]) for alert in alerts]
        max_severity = max(severities, key=lambda severity: severity.order)
        return str(max_severity)

    def run_rules(self, events: list[AlertDto]):
        self.logger.info("Running rules")
        rules = get_rules_db(tenant_id=self.tenant_id)

        groups = []
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
                    group_fingerprint = self._calc_group_fingerprint(event, rule)
                    # Add relation between this event and the group
                    updated_group = assign_alert_to_group_db(
                        tenant_id=self.tenant_id,
                        alert_id=event.event_id,
                        rule_id=str(rule.id),
                        timeframe=rule.timeframe,
                        group_fingerprint=group_fingerprint,
                    )
                    groups.append(updated_group)
                else:
                    self.logger.info(
                        f"Rule {rule.name} on event {event.id} is not relevant"
                    )
        self.logger.info("Rules ran successfully")
        # if we don't have any updated groups, we don't need to create any alerts
        if not groups:
            return
        # get the rules of the groups
        updated_group_rule_ids = [group.rule_id for group in groups]
        updated_rules = get_rules_db(
            tenant_id=self.tenant_id, ids=updated_group_rule_ids
        )
        # more convenient to work with a dict
        updated_rules_dict = {str(rule.id): rule for rule in updated_rules}
        # Now let's create a new alert for each group
        grouped_alerts = []
        for group in groups:
            rule = updated_rules_dict.get(str(group.rule_id))
            group_fingerprint = group.calculate_fingerprint()
            try:
                group_attributes = GroupDto.get_group_attributes(group.alerts)
            except Exception:
                # should not happen since I fixed the assign_alert_to_group_db
                self.logger.exception(
                    f"Failed to calculate group attributes for group {group.id}"
                )
                continue
            context = {
                "group_attributes": group_attributes,
                # Shahar: first, group have at least one alert.
                #         second, the only supported {{ }} are the ones in the group
                #          attributes, so we can use the first alert because they are the same for any other alert in the group
                **group.alerts[0].event,
            }
            group_description = chevron.render(rule.group_description, context)
            group_severity = self._calc_max_severity(group.alerts)
            # group all the sources from all the alerts
            group_source = list(
                set(
                    itertools.chain.from_iterable(
                        [alert.event["source"] for alert in group.alerts]
                    )
                )
            )
            # inert "keep" as the first source to emphasize that this alert was generated by keep
            group_source.insert(0, "keep")
            # if the group has "group by", add it to the group name
            if rule.grouping_criteria:
                group_name = f"Alert group genereted by rule {rule.name} | group:{group.group_fingerprint}"
            else:
                group_name = f"Alert group genereted by rule {rule.name}"

            group_status = self._calc_group_status(group.alerts)
            # get the payload of the group
            # todo: this is not scaling, needs to find another solution
            # group_payload = self._generate_group_payload(group.alerts)
            # create the alert
            group_alert = create_alert_db(
                tenant_id=self.tenant_id,
                provider_type="group",
                provider_id=rule.id,
                # todo: event should support list?
                event={
                    "name": group_name,
                    "id": group_fingerprint,
                    "description": group_description,
                    "lastReceived": group_attributes.get("last_update_time"),
                    "severity": group_severity,
                    "source": group_source,
                    "status": group_status,
                    "pushed": True,
                    "group": True,
                    # "groupPayload": group_payload,
                    "fingerprint": group_fingerprint,
                    **group_attributes,
                },
                fingerprint=group_fingerprint,
            )
            grouped_alerts.append(group_alert)
            self.logger.info(f"Created alert {group_alert.id} for group {group.id}")
        self.logger.info(f"Rules ran, {len(grouped_alerts)} alerts created")
        alerts_dto = [AlertDto(**alert.event) for alert in grouped_alerts]
        return alerts_dto

    def _extract_subrules(self, expression):
        # CEL rules looks like '(source == "sentry") && (source == "grafana" && severity == "critical")'
        # and we need to extract the subrules
        sub_rules = expression.split(") && (")
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
        env = celpy.Environment()
        for sub_rule in sub_rules:
            ast = env.compile(sub_rule)
            prgm = env.program(ast)
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

    def _calc_group_fingerprint(self, event: AlertDto, rule):
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
        # than the group_fingerprint will be "queue1,cluster1"

        # note: group_fingerprint is not a unique id, since different rules can lead to the same group_fingerprint
        #       hence, the actual fingerprint is composed of the group_fingerprint and the group id
        event_payload = event.dict()
        grouping_criteria = rule.grouping_criteria or []
        group_fingerprint = []
        for criteria in grouping_criteria:
            # we need to extract the value from the event
            # e.g. if the criteria is "event.labels.queue"
            # than we need to extract the value of event["labels"]["queue"]
            criteria_parts = criteria.split(".")
            value = event_payload
            for part in criteria_parts:
                value = value.get(part)
            group_fingerprint.append(value)
        # if, for example, the event should have labels.X but it doesn't,
        # than we will have None in the group_fingerprint
        if not group_fingerprint:
            self.logger.warning(
                f"Failed to calculate group fingerprint for event {event.id} and rule {rule.name}"
            )
            return "none"
        # if any of the values is None, we will return "none"
        if any([fingerprint is None for fingerprint in group_fingerprint]):
            self.logger.warning(
                f"Failed to fetch the appropriate labels from the event {event.id} and rule {rule.name}"
            )
            return "none"
        return ",".join(group_fingerprint)

    def _calc_group_status(self, alerts):
        """This function calculates the status of a group of alerts according to the following logic:
        1. If the last alert of each fingerprint is resolved, the group is resolved
        2. If at least one of the alerts is firing, the group is firing


        Args:
            alerts (list[Alert]): list of alerts related to the group

        Returns:
            AlertStatus: the alert status (enum)
        """
        # take the last alert from each fingerprint
        # if all of them are resolved, the group is resolved
        alerts_by_fingerprint = {}
        for alert in alerts:
            if alert.fingerprint not in alerts_by_fingerprint:
                alerts_by_fingerprint[alert.fingerprint] = [alert]
            else:
                alerts_by_fingerprint[alert.fingerprint].append(alert)

        # now take the latest (by timestamp) for each fingerprint:
        alerts = [
            max(alerts, key=lambda alert: alert.event["lastReceived"])
            for alerts in alerts_by_fingerprint.values()
        ]
        # 1. if all alerts are with the same status, just use it
        if len(set(alert.event["status"] for alert in alerts)) == 1:
            return alerts[0].event["status"]
        # 2. Else, if at least one of them is firing, the group is firing
        if any(alert.event["status"] == AlertStatus.FIRING for alert in alerts):
            return AlertStatus.FIRING
        # 3. Last, just return the last status
        return alerts[-1].event["status"]

    def _generate_group_payload(self, alerts):
        # todo: group payload should be configurable
        """This function generates the payload of the group alert.

        Args:
            alerts (list[Alert]): list of alerts related to the group

        Returns:
            dict: the payload of the group alert
        """

        # first, group by fingerprints
        alerts_by_fingerprint = {}
        for alert in alerts:
            if alert.fingerprint not in alerts_by_fingerprint:
                alerts_by_fingerprint[alert.fingerprint] = [alert]
            else:
                alerts_by_fingerprint[alert.fingerprint].append(alert)

        group_payload = {}
        for fingerprint, alerts in alerts_by_fingerprint.items():
            # take the latest (by timestamp) for each fingerprint:
            alert = max(alerts, key=lambda alert: alert.event["lastReceived"])
            group_payload[fingerprint] = {
                "name": alert.event["name"],
                "number_of_alerts": len(alerts),
                "fingerprint": fingerprint,
                "last_status": alert.event["status"],
                "last_severity": alert.event["severity"],
            }

        return group_payload

    @staticmethod
    def preprocess_cel_expression(cel_expression: str) -> str:
        """Preprocess CEL expressions to replace string-based comparisons with numeric values where applicable."""

        # Construct a regex pattern that matches any severity level or other comparisons
        # and accounts for both single and double quotes as well as optional spaces around the operator
        severities = "|".join(
            [f"\"{severity.value}\"|'{severity.value}'" for severity in AlertSeverity]
        )
        pattern = rf"(\w+)\s*([=><!]=?)\s*({severities})"

        def replace_matched(match):
            field_name, operator, matched_value = (
                match.group(1),
                match.group(2),
                match.group(3).strip("\"'"),
            )

            # Handle severity-specific replacement
            if field_name.lower() == "severity":
                severity_order = next(
                    (
                        severity.order
                        for severity in AlertSeverity
                        if severity.value == matched_value.lower()
                    ),
                    None,
                )
                if severity_order is not None:
                    return f"{field_name} {operator} {severity_order}"

            # Return the original match if it's not a severity comparison or if no replacement is necessary
            return match.group(0)

        modified_expression = re.sub(
            pattern, replace_matched, cel_expression, flags=re.IGNORECASE
        )

        return modified_expression

    @staticmethod
    def filter_alerts(alerts: list[AlertDto], cel: str):
        """This function filters alerts according to a CEL

        Args:
            alerts (list[AlertDto]): list of alerts
            cel (str): CEL expression

        Returns:
            list[AlertDto]: list of alerts that are related to the cel
        """
        logger = logging.getLogger(__name__)
        env = celpy.Environment()
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
        cel = RulesEngine.preprocess_cel_expression(cel)
        ast = env.compile(cel)
        prgm = env.program(ast)
        filtered_alerts = []
        for alert in alerts:
            payload = alert.dict()
            # TODO: workaround since source is a list
            #       should be fixed in the future
            payload["source"] = ",".join(payload["source"])
            # payload severity could be the severity itself or the order of the severity, cast it to the order
            if isinstance(payload["severity"], str):
                payload["severity"] = AlertSeverity(payload["severity"].lower()).order

            activation = celpy.json_to_cel(json.loads(json.dumps(payload, default=str)))
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
