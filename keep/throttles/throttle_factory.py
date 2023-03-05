import importlib

from keep.throttles.base_throttle import BaseThrottle


class ThrottleFactory:
    @staticmethod
    def get_instance(throttle_type, throttle_config) -> BaseThrottle:
        module = importlib.import_module(f"keep.throttles.{throttle_type}_throttle")
        throttle_class = getattr(
            module, throttle_type.title().replace("_", "") + "Throttle"
        )
        return throttle_class(throttle_type, throttle_config)
