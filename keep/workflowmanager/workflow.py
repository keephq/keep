import enum
import typing

from keep.contextmanager.contextmanager import ContextManager
from keep.iohandler.iohandler import IOHandler
from keep.step.step import Step, StepError


class WorkflowStrategy(enum.Enum):
    # if a workflow run on the same fingerprint, skip the workflow
    NONPARALLEL = "nonparallel"
    # if a workflow run on the same fingerprint, add the workflow back to the queue and run it again on the next cycle
    NONPARALLEL_WITH_RETRY = "nonparallel_with_retry"  # DEFAULT
    # if a workflow run on the same fingerprint, run
    PARALLEL = "parallel"


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
        workflow_disabled: bool = False,
        workflow_providers: typing.List[dict] = None,
        workflow_providers_type: typing.List[str] = [],
        workflow_strategy: WorkflowStrategy = WorkflowStrategy.NONPARALLEL_WITH_RETRY.value,
        on_failure: Step = None,
        workflow_consts: typing.Dict[str, str] = {},
    ):
        self.workflow_id = workflow_id
        self.workflow_owners = workflow_owners
        self.workflow_tags = workflow_tags
        self.workflow_interval = workflow_interval
        self.workflow_triggers = workflow_triggers
        self.workflow_steps = workflow_steps
        self.workflow_actions = workflow_actions
        self.workflow_description = workflow_description
        self.workflow_disabled = workflow_disabled
        self.workflow_providers = workflow_providers
        self.workflow_providers_type = workflow_providers_type
        self.workflow_strategy = workflow_strategy
        self.workflow_consts = workflow_consts
        self.on_failure = on_failure
        self.context_manager = context_manager
        self.context_manager.set_consts_context(workflow_consts)
        self.io_nandler = IOHandler(context_manager)
        self.logger = self.context_manager.get_logger()

    async def run_steps(self):
        self.logger.debug(f"Running steps for workflow {self.workflow_id}")
        for step in self.workflow_steps:
            try:
                self.logger.info("Running step %s", step.step_id)
                step_ran = await step.run()
                if step_ran:
                    self.logger.info("Step %s ran successfully", step.step_id)
            except StepError as e:
                self.logger.error(f"Step {step.step_id} failed: {e}")
                raise
        self.logger.debug(f"Steps for workflow {self.workflow_id} ran successfully")

    async def run_action(self, action: Step):
        self.logger.info("Running action %s", action.name)
        try:
            action_ran = await action.run()
            action_error = None
            if action_ran:
                self.logger.info("Action %s ran successfully", action.name)
        except Exception as e:
            self.logger.error(f"Action {action.name} failed: {e}")
            action_ran = False
            action_error = f"Failed to run action {action.name}: {str(e)}"
        return action_ran, action_error

    async def run_actions(self):
        self.logger.debug("Running actions")
        actions_firing = []
        actions_errors = []
        for action in self.workflow_actions:
            action_status, action_error = await self.run_action(action)
            if action_error:
                actions_firing.append(action_status)
                actions_errors.append(action_error)
        self.logger.debug("Actions run")
        return actions_firing, actions_errors

    async def run(self, workflow_execution_id):
        if self.workflow_disabled:
            self.logger.info(f"Skipping disabled workflow {self.workflow_id}")
            return
        self.logger.info(f"Running workflow {self.workflow_id}")
        self.context_manager.set_execution_context(workflow_execution_id)
        try:
            await self.run_steps()
        except StepError as e:
            self.logger.error(
                f"Workflow {self.workflow_id} failed: {e}",
                extra={
                    "workflow_execution_id": workflow_execution_id,
                },
            )
            raise
        actions_firing, actions_errors = self.run_actions()
        self.logger.info(f"Finish to run workflow {self.workflow_id}")
        return actions_errors

    async def _handle_actions(self):
        self.logger.debug(f"Handling actions for workflow {self.workflow_id}")
        for action in self.workflow_actions:
            await action.run()
        self.logger.debug(f"Actions handled for workflow {self.workflow_id}")
