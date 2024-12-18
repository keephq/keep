# tracking.py
import uuid

import memray


class MemrayTracker:
    def __init__(self):
        self.tracker = None
        self.tracking_file = None

    def start(self):
        if self.tracker:
            return

        # Create temporary file that will exist through app lifetime
        self.tracking_file_name = f"/tmp/memray_{str(uuid.uuid4())}"
        self.tracker = memray.Tracker(
            self.tracking_file_name,
            native_traces=True,
            trace_python_allocators=True,
            aggregated=True,
        )
        self.tracker.__enter__()

    def stop(self):
        if self.tracker:
            self.tracker.__exit__(None, None, None)
            self.tracker = None

    def get_tracking_file(self):
        return self.tracking_file_name if self.tracking_file_name else None


# Global instance
memory_tracker = MemrayTracker()
