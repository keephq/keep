import enum
import typing

from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.step.step import Step, StepError


class WorkflowStatus(enum.Enum):
    RESOLVED = "resolved"
    FIRING = "firing"


class Workflow:
    def __init__(
        self,
        context_manager: ContextManager,
        workflow_id: str,
        workflow_owners: typing.List[str],
        workflow_tags: typing.List[str],
        workflow_interval: int,
        workflow_triggers: typing.Optional[typing.List[dict]],
        workflow_steps: typing.List[Step],
        workflow_actions: typing.List[Step],
        workflow_description: str = None,
        workflow_providers: typing.List[dict] = None,
        workflow_providers_type: typing.List[str] = [],
        on_failure: Step = None,
    ):
        self.workflow_id = workflow_id
        self.workflow_owners = workflow_owners
        self.workflow_tags = workflow_tags
        self.workflow_interval = workflow_interval
        self.workflow_triggers = workflow_triggers
        self.workflow_steps = workflow_steps
        self.workflow_actions = workflow_actions
        self.workflow_description = workflow_description
        self.workflow_providers = workflow_providers
        self.workflow_providers_type = workflow_providers_type
        self.on_failure = on_failure
        self.context_manager = context_manager
        self.io_nandler = IOHandler(context_manager)
        self.logger = self.context_manager.get_logger()

    def run_step(self, step: Step):
        self.logger.info("Running step %s", step.step_id)
        if step.foreach:
            rendered_foreach = self.io_nandler.render(step.foreach)
            for f in rendered_foreach:
                self.logger.debug("Step is a foreach step")
                self.context_manager.set_for_each_context(f)
                step.run()
        else:
            step.run()
        self.logger.info("Step %s ran successfully", step.step_id)

    def run_steps(self):
        self.logger.debug(f"Running steps for workflow {self.workflow_id}")
        for step in self.workflow_steps:
            try:
                self.run_step(step)
            except StepError as e:
                self.logger.error(f"Step {step.step_id} failed: {e}")
                raise
        self.logger.debug(f"Steps for workflow {self.workflow_id} ran successfully")

    def run_action(self, action: Step):
        self.logger.info("Running action %s", action.name)
        try:
            action_status = action.run()
            action_error = None
            self.logger.info("Action %s ran successfully", action.name)
        except Exception as e:
            self.logger.error(f"Action {action.name} failed: {e}")
            action_status = False
            action_error = str(e)
        return action_status, action_error

    def run_actions(self):
        self.logger.debug("Running actions")
        actions_firing = []
        actions_errors = []
        for action in self.workflow_actions:
            action_status, action_error = self.run_action(action)
            actions_firing.append(action_status)
            actions_errors.append(action_error)
        self.logger.debug("Actions run")
        return actions_firing, actions_errors

    def run(self, workflow_execution_id):
        self.logger.info(f"Running workflow {self.workflow_id}")
        self.context_manager.set_execution_context(workflow_execution_id)
        try:
            self.run_steps()
        except StepError as e:
            self.logger.error(
                f"Workflow {self.workflow_id} failed: {e}",
                extra={
                    "workflow_execution_id": workflow_execution_id,
                },
            )
            raise
        actions_firing, actions_errors = self.run_actions()
        # Save the state
        #   workflow is firing if one its actions is firing
        workflow_status = (
            WorkflowStatus.FIRING.value
            if any(actions_firing)
            else WorkflowStatus.RESOLVED.value
        )
        # TODO: state management should be done in db (how will it work distributed?)
        self.context_manager.set_last_workflow_run(
            workflow_id=self.workflow_id,
            workflow_context={
                "steps_context": self.context_manager.steps_context,
            },
            workflow_status=workflow_status,
        )
        self.logger.info(f"Finish to run workflow {self.workflow_id}")
        return actions_errors

    def _handle_actions(self):
        self.logger.debug(f"Handling actions for workflow {self.workflow_id}")
        for action in self.workflow_actions:
            action.run()
        self.logger.debug(f"Actions handled for workflow {self.workflow_id}")

    def run_missing_steps(self, end_step=None):
        """Runs steps without context (when the workflow is run by the API)"""
        self.logger.debug(f"Running missing steps for workflow {self.workflow_id}")
        steps_context = self.context_manager.get_full_context().get("steps")
        for step in self.workflow_steps:
            # if we reached the end step, stop
            if end_step and step.step_id == end_step.step_id:
                break
            # If we don't have context for the step, run it
            if step.step_id not in steps_context:
                try:
                    self.run_step(step)
                except StepError as e:
                    self.logger.error(f"Step {step.step_id} failed: {e}")
                    raise
        self.logger.debug(
            f"Missing steps for workflow {self.workflow_id} ran successfully"
        )
