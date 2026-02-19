from keep.api.core.db import get_alert_by_fingerprint_and_event_id, \
    get_workflow_to_alert_execution_by_workflow_execution_id
from keep.api.models.alert import AlertStatus
from keep.throttles.base_throttle import BaseThrottle
from keep.contextmanager.contextmanager import ContextManager


class OneUntilResolvedThrottle(BaseThrottle):
    """OneUntilResolvedThrottle if action is throttled by checking if the last time the .

    Args:
        BaseThrottle (_type_): _description_
    """

    def __init__(self, context_manager: ContextManager, throttle_type, throttle_config):
        super().__init__(context_manager=context_manager, throttle_type=throttle_type, throttle_config=throttle_config)

    def check_throttling(self, action_name, workflow_id, event_id, **kwargs) -> bool:
        last_workflow_run = self.context_manager.get_last_workflow_run(workflow_id)
        if not last_workflow_run:
            return False

        # query workflowtoalertexecution table by workflow_id and after that get the alert by fingerprint and event_id
        last_workflow_alert_execution = get_workflow_to_alert_execution_by_workflow_execution_id(last_workflow_run.id)
        if not last_workflow_alert_execution:
            return False

        alert = get_alert_by_fingerprint_and_event_id(self.context_manager.tenant_id,
                                              last_workflow_alert_execution.alert_fingerprint,
                                              last_workflow_alert_execution.event_id)
        if not alert:
            return False

        # if the last time the alert were triggered it was in resolved status, return false
        if AlertStatus(alert.event.get("status")) == AlertStatus.RESOLVED:
            return False

        # else, return true because its already firing
        return True
