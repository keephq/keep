import logging
import typing

from keep.action.action import Action
from keep.contextmanager.contextmanager import ContextManager
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
    ):
        self.logger = logging.getLogger(__name__)
        self.alert_id = alert_id
        self.alert_owners = alert_owners
        self.alert_tags = alert_tags
        self.alert_steps = alert_steps
        self.alert_actions = alert_actions
        self.io_nandler = IOHandler()
        self.context_manager = ContextManager.get_instance()

    @property
    def last_step(self):
        return self.alert_steps[-1]

    def run(self):
        self.logger.debug(f"Running alert {self.alert_id}")
        for step in self.alert_steps:
            try:
                self.logger.info("Running step %s", step.step_id)
                step.run()
                self.logger.info("Step %s ran successfully", step.step_id)
                # If we need to halt the alert, stop here
                if step.action_needed:
                    self.logger.info(
                        f"Step {str(step.step_id)} got positive output, running actions and stopping",
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
            step.handle_failure_strategy(step)
        else:
            self.logger.exception("Failed to run step")
            raise StepError(
                f"Step {step.step_id} failed to execute without error handling strategy - {str(exc)}",
            )

    def _handle_actions(self):
        self.logger.debug(f"Handling actisons for alert {self.alert_id}")
        for action in self.alert_actions:
            action.run()
        self.logger.debug(f"Actions handled for alert {self.alert_id}")
