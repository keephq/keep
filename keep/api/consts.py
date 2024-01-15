import os

RUNNING_IN_CLOUD_RUN = os.environ.get("K_SERVICE") is not None
