import logging
import re

import celpy

from keep.api.core.db import get_rules as get_rules_db
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
                rule_result = self._run_rule_on_event(rule, event)
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
            self._run_rule(rule, events)
        return []

    def _split_by_parentheses(self, expression):
        # This regex will match content within parentheses
        matches = re.findall(r"\(([^)]+)\)", expression)
        return matches

    # TODO: a lot of unit tests to write here
    def _run_rule_on_event(self, rule, event: AlertDto):
        sub_rules = self._split_by_parentheses(rule.definition_cel)
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
        pass
