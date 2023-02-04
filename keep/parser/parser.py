import logging
import typing

import yaml

from keep.action.action import Action
from keep.alert.alert import Alert
from keep.step.step import Step


class Parser:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def parse(self, file):
        self.logger.debug(f"Parsing {file}")
        with open(file, "r") as file:
            alert = yaml.safe_load(file)
        self.logger.debug(f"Alert {file} parsed successfully")
        alert_id = self._parse_id(alert)
        alert_owners = self._parse_owners(alert)
        alert_tags = self._parse_tags(alert)
        alert_steps = self._parse_steps(alert)
        alert_actions = self._parse_action(alert)
        alert = Alert(alert_id, alert_owners, alert_tags, alert_steps, alert_actions)
        self.logger.debug(f"Alert {file} parsed successfully")
        return alert

    def _parse_id(self, alert) -> str:
        alert_id = alert.get("alert_id")
        if alert_id is None:
            raise ValueError("Alert ID is required")
        return alert_id

    def _parse_owners(self, alert) -> typing.List[str]:
        alert_owners = alert.get("alert_owners", [])
        return alert_owners

    def _parse_tags(self, alert) -> typing.List[str]:
        alert_tags = alert.get("alert_tags", [])
        return alert_tags

    def _parse_steps(self, alert) -> typing.List[Step]:
        self.logger.debug("Parsing steps")
        alert_steps = alert.get("alert_steps", [])
        alerts_steps_parsed = []
        for _step in alert_steps:
            step = Step(**_step)
            alerts_steps_parsed.append(step)
        self.logger.debug("Steps parsed successfully")
        return alerts_steps_parsed

    def _parse_action(self, alert) -> typing.List[Action]:
        self.logger.debug("Parsing actions")
        alert_actions = alert.get("alert_actions", [])
        alert_actions_parsed = []
        for _action in alert_actions:
            action = Action(**_action)
            alert_actions_parsed.append(action)
        self.logger.debug("Actions parsed successfully")
        return alert_actions_parsed
