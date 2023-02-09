import logging
import typing

from keep.action.action import Action
from keep.iohandler.iohandler import IOHandler
from keep.step.step import Step, StepError


class Alert:
    def __init__(
        self,
        alert_id: str,
        alert_owners: typing.List[str],
        alert_tags: typing.List[str],
        alert_steps: typing.List[Step],
        alert_actions: typing.List[Action],
        providers_config: typing.Dict[str, dict],
    ):
        self.logger = logging.getLogger(__name__)
        self.alert_id = alert_id
        self.alert_owners = alert_owners
        self.alert_tags = alert_tags
        self.alert_steps = alert_steps
        self.alert_actions = alert_actions
        self.providers_config = providers_config
        self.io_nandler = IOHandler()
        self.steps_context = {}

    @property
    def last_step(self):
        return self.alert_steps[-1]

    def run(self):
        self.logger.debug(f"Running alert {self.alert_id}")
        for step in self.alert_steps:
            try:
                self.logger.info("Running step %s", step.step_id)
                step_output = step.run(self.full_context)
                self.logger.info("Step %s ran successfully", step.step_id)
                self.steps_context[step.step_id] = {
                    "output": step_output,
                }
                # If we need to halt the alert, stop here
                if step.action_needed:
                    self.logger.info(
                        f"Step {str(step.step_id)} got positive output, running actions and stopping"
                    )
                    self._handle_actions()
                    return  # <--- stop HERE
            except StepError as e:
                self.logger.error(f"Step {step.step_id} failed: {e}")
                self._handle_failure(step, e)

        self.logger.debug(f"Alert {self.alert_id} ran successfully")

    def _handle_failure(self, step: Step, exc):
        # if the step has failure strategy, handle it
        if step.failure_strategy:
            step.handle_failure_strategy(step, self.full_context)
        else:
            self.logger.exception("Failed to run step")
            raise StepError(
                f"Step {step.step_id} failed to execute without error handling strategy - {str(exc)}"
            )

    def _handle_actions(self):
        self.logger.debug(f"Handling actisons for alert {self.alert_id}")
        for action in self.alert_actions:
            action.run(self.full_context)
        self.logger.debug(f"Actions handled for alert {self.alert_id}")

    @property
    def full_context(self):
        return {"providers": self.providers_config, "steps": self.steps_context}
