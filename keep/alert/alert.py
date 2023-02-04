import logging
import typing

from keep.action.action import Action
from keep.step.step import Step, StepError


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
        self.alert_context = {}

    def run(self):
        self.logger.debug(f"Running alert {self.alert_id}")
        for step in self.steps:
            try:
                step_output = step.run(self.alert_context)
            except StepError as e:
                self.logger.error(f"Step {step.step_id} failed: {e}")
                self._handle_failure(step)
        self.logger.debug(f"Alert {self.alert_id} ran successfully")

    def _handle_failure(self, step: Step):
        self.logger.debug(f"Handling failure for step {step.step_id}")
        for action in self.alert_actions:
            action.run(step)
        self.logger.debug(f"Failure handled for step {step.step_id}")
