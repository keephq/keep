import logging
import typing

from keep.action.action import Action
from keep.step.step import Step


class Alert:
    def __init__(
        self,
        alert_id: str,
        alert_owners: typing.List[str],
        alert_tags: typeing.List[str],
        alert_steps: typing.List[Step],
        alert_actions: typing.List[Action],
    ):
        self.logger = logging.getLogger(__name__)
        self.alert_id = alert_id
        self.alert_owners = alert_owners
        self.alert_tags = alert_tags
        self.alert_steps = alert_steps
        self.alert_actions = alert_actions

    def run(self):
        self.logger.debug(f"Running alert {self.alert_id}")
        self.logger.debug(f"Alert {self.alert_id} ran successfully")
