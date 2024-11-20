import sys

# It's a dirty hack to exclude current directory from sys.path
# to avoid importing "logging.py" located in the same directory
# instead of the standard library "logging" module.
# TODO: rename logging.py
for i in range(0, len(sys.path)):
    if "keep/api" in sys.path[i]:
        sys.path.pop(i)
        break

import os
import time
import logging
import requests

from keep.api.core.demo_mode import launch_demo_mode_thread
from keep.api.core.report_uptime import launch_uptime_reporting_thread

logger = logging.getLogger(__name__)


def main():
    logger.info("Starting background server jobs.")

    # We intentionally don't use KEEP_API_URL here to avoid going through the internet.
    # Demo mode should be launched in the same environment as the server.
    keep_api_url = "http://localhost:" + str(os.environ.get("PORT", 8080))

    while True:
        try:
            logger.info(f"Checking if server is up at {keep_api_url}...")
            response = requests.get(keep_api_url)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException:
            logger.info("API is not up yet. Waiting...")
            time.sleep(5)

    threads = []
    threads.append(launch_demo_mode_thread(keep_api_url))
    threads.append(launch_uptime_reporting_thread())
    
    for thread in threads:
        if thread is not None:
            thread.join()

    logger.info("Background server jobs started.")


if __name__ == "__main__":
    """
    This script should be executed alongside to the server.
    Running it in the same process as the server may (and most probably will) cause issues.
    """
    main()
