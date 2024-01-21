import json
import logging

import celpy

from keep.api.core.db import assign_alert_to_group as assign_alert_to_group_db
from keep.api.core.db import get_rules as get_rules_db
from keep.api.models.alert import AlertDto


class RulesEngine:
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(__name__)

    def _calc_max_severity(self, severities):
        # TODO: this is a naive implementation, we should normaliaze all the severities from all providers and calculate the max
        # TODO 2: this could be also be configured by the user ("more than 5 highs => critical")

        # if we don't have any severities, we fallback to info
        if not severities:
            self.logger.info(
                "Could not calculate max severity from empty list - fallbacking to info"
            )
            return "info"
        severities_lower = [severity.lower() for severity in severities]
        # fatal is the highest severity
        if "fatal" in severities_lower:
            return "fatal"
        # critical is the second highest severity
        if "critical" in severities_lower:
            return "critical"
        if "high" in severities_lower:
            return "high"
        if "medium" in severities_lower:
            return "medium"
        if "low" in severities_lower:
            return "low"
        # if none of the severities are fatal, critical, high, medium or low, we fallback to the first severity
        self.logger.info(
            f"Could not calculate max severity from {severities} - fallbacking"
        )
        return severities[0]

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
                        group_fingerprint=group_fingerprint,
                    )
                    groups.append(updated_group)
                else:
                    self.logger.info(
                        f"Rule {rule.name} on event {event.id} is not relevant"
                    )
        self.logger.info("Rules ran successfully")
        # todo: do something with the groups
        #       such as trigger webhook with the group ids
        pass

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
            r = prgm.evaluate(activation)
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
        event_payload = event.dict()
        grouping_criteria = rule.grouping_criteria
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
        return ",".join(group_fingerprint)
