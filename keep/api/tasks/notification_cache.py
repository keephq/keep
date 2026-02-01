import os
import time
from typing import Dict, Tuple

# Get polling interval from env
POLLING_INTERVAL = int(os.getenv("PUSHER_POLLING_INTERVAL", "15"))


class NotificationCache:
    _instance = None
    __initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self.__initialized:
            self.cache: Dict[Tuple[str, str], float] = {}
            self.__initialized = True

    def should_notify(self, tenant_id: str, event_type: str) -> bool:
        cache_key = (tenant_id, event_type)
        current_time = time.time()

        if cache_key not in self.cache:
            self.cache[cache_key] = current_time
            return True

        last_time = self.cache[cache_key]
        if current_time - last_time >= POLLING_INTERVAL:
            self.cache[cache_key] = current_time
            return True

        return False


# Get singleton instance
def get_notification_cache() -> NotificationCache:
    return NotificationCache()
