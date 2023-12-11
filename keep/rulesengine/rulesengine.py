import logging

import celpy

from keep.api.core.db import get_rules as get_rules_db
from keep.api.core.db import run_rule as run_rule_db
from keep.api.models.alert import AlertDto


class RulesEngine:
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id
        self.logger = logging.getLogger(__name__)

    def run_rules(self, events: list[AlertDto]):
        self.logger.info("Running rules")
        rules = get_rules_db(tenant_id=self.tenant_id)

        # first, we need to understand which rules are actually relevant for the events that arrived
        relevent_rules_for_events = []
        for rule in rules:
            self.logger.info(f"Running rule {rule.name}")
            for event in events:
                self.logger.info(f"Running rule {rule.name} on event {event.id}")
                try:
                    rule_result = self._run_rule_on_event(rule, event)
                except Exception:
                    self.logger.exception(
                        f"Failed to run rule {rule.name} on event {event.id}"
                    )
                    continue
                if rule_result:
                    self.logger.info(
                        f"Rule {rule.name} on event {event.id} is relevant"
                    )
                    relevent_rules_for_events.append(rule)
                else:
                    self.logger.info(
                        f"Rule {rule.name} on event {event.id} is not relevant"
                    )

        self.logger.info("Rules ran, creating alerts")
        # Create the alerts if needed
        for rule in relevent_rules_for_events:
            self.logger.info(f"Running relevant rule {rule.name}")
            self._run_rule(rule)
        return []

    def _extract_subrules(self, expression):
        # CEL rules looks like '(source == "sentry") && (source == "grafana" && severity == "critical")'
        # and we need to extract the subrules
        sub_rules = expression.split(") && (")
        # the first and the last rules will have a ( or ) at the beginning or the end
        sub_rules[0] = sub_rules[0][1:]
        sub_rules[-1] = sub_rules[-1][:-1]
        return sub_rules

    # TODO: a lot of unit tests to write here
    def _run_rule_on_event(self, rule, event: AlertDto):
        sub_rules = self._extract_subrules(rule.definition_cel)
        payload = event.dict()
        # workaround since source is a list
        # todo: fix this in the future
        payload["source"] = payload["source"][0]
        for sub_rule in sub_rules:
            env = celpy.Environment()
            ast = env.compile(sub_rule)
            prgm = env.program(ast)
            r = prgm.evaluate(payload)
            if r:
                return True
        # no subrules matched
        return False

    def _run_rule(self, rule):
        # prepare the rule
        rule_results = run_rule_db(tenant_id=self.tenant_id, rule=rule)
        if not rule_results:
            self.logger.info(f"Rule {rule.name} does not apply.")
            return

        self.logger.info(f"Rule {rule.name} applies.")
        # create aggregated alert from the results
        return rule_results
