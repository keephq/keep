from keep.throttles.base_throttle import BaseThrottle


class OneUntilResolvedThrottle(BaseThrottle):
    """OneUntilResolvedThrottle if action is throttled by checking if the last time the .

    Args:
        BaseThrottle (_type_): _description_
    """

    def __init__(self, throttle_type, throttle_config):
        super().__init__(throttle_type, throttle_config)

    def check_throttling(self, action_name, alert_id, **kwargs) -> bool:
        last_alert_run = self.context_manager.get_last_workflow_run(alert_id)
        if not last_alert_run:
            return False
        # if the last time the alert were triggered it was in resolved status, return false
        if last_alert_run.get("alert_status").lower() == "resolved":
            return False
        # else, return true because its already firing
        return True
