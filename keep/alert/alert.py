import enum
import logging
import typing

from pydantic.dataclasses import dataclass

from keep.action.action import Action
from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.statemanager.statemanager import StateManager
from keep.step.step import Step, StepError


class AlertStatus(enum.Enum):
    RESOLVED = "resolved"
    FIRING = "firing"


@dataclass
class Alert:
    alert_id: str
    alert_source: str
    alert_owners: typing.List[str]
    alert_tags: typing.List[str]
    alert_steps: typing.List[Step]
    alert_actions: typing.List[Action]
    alert_file: str = None

    def __post_init__(self):
        self.logger = logging.getLogger(__name__)
        self.alert_file = self.alert_source.split("/")[-1]
        self.io_nandler = IOHandler()
        self.context_manager = ContextManager.get_instance()
        self.state_manager = StateManager.get_instance()
        # keep the state of the steps
        self.steps_ran = {step.step_id: False for step in self.alert_steps}

    def _get_alert_context(self):
        return {
            "alert_id": self.alert_id,
            "alert_owners": self.alert_owners,
            "alert_tags": self.alert_tags,
        }

    def run_step(self, step: Step):
        self.logger.info("Running step %s", step.step_id)
        step_output = step.run()
        self.steps_ran[step.step_id] = True
        self.logger.info("Step %s ran successfully", step.step_id)
        return step_output

    def run_steps(self):
        self.logger.debug(f"Running steps for alert {self.alert_id}")
        for step in self.alert_steps:
            try:
                self.run_step(step)
            except StepError as e:
                self.logger.error(f"Step {step.step_id} failed: {e}")
                self._handle_failure(step, e)
                raise
        self.logger.debug(f"Steps for alert {self.alert_id} ran successfully")

    def run_action(self, action: Action):
        self.logger.info("Running action %s", action.name)
        try:
            action_status = action.run()
            self.logger.info("Action %s ran successfully", action.name)
        except Exception as e:
            self.logger.error(f"Action {action.name} failed: {e}")
            raise
        self.logger.info("Action %s ran successfully", action.name)
        return action_status

    def run_actions(self):
        self.logger.debug("Running actions")
        actions_firing = []
        for action in self.alert_actions:
            actions_firing.append(self.run_action(action))
        self.logger.debug("Actions ran successfully")
        return actions_firing

    def run(self):
        self.logger.debug(f"Running alert {self.alert_id}")
        self.context_manager.set_alert_context(self._get_alert_context())
        self.run_steps()
        actions_firing = self.run_actions()

        # Save the state
        #   alert is firing if one its actions is firing
        alert_status = (
            AlertStatus.FIRING.value
            if any(actions_firing)
            else AlertStatus.RESOLVED.value
        )
        self.state_manager.set_last_alert_run(
            alert_id=self.alert_id,
            alert_context=self._get_alert_context(),
            alert_status=alert_status,
        )
        self.logger.debug(f"Alert {self.alert_id} ran successfully")

    def _handle_failure(self, step: Step, exc):
        # if the step has failure strategy, handle it
        if step.failure_strategy:
            step.handle_failure_strategy(step)
        else:
            self.logger.exception("Failed to run step")
            raise StepError(
                f"Step {step.step_id} failed to execute without error handling strategy - {str(exc)}"
            )

    def _handle_actions(self):
        self.logger.debug(f"Handling actions for alert {self.alert_id}")
        for action in self.alert_actions:
            action.run()
        self.logger.debug(f"Actions handled for alert {self.alert_id}")
