import asyncio
import logging
import os
import sys

from dotenv import find_dotenv, load_dotenv
from gunicorn.workers.sync import SyncWorker

import keep.api.logging
from keep.api.arq_worker import get_arq_worker, safe_run_worker
from keep.api.consts import (
    KEEP_ARQ_QUEUE_BASIC,
    KEEP_ARQ_TASK_POOL,
    KEEP_ARQ_TASK_POOL_ALL,
    KEEP_ARQ_TASK_POOL_BASIC_PROCESSING,
    KEEP_ARQ_TASK_POOL_NONE,
)
from keep.api.core.config import config
from keep.api.core.db import dispose_session
from keep.workflowmanager.workflowmanager import WorkflowManager

# Load environment variables
load_dotenv(find_dotenv())
keep.api.logging.setup_logging()
logger = logging.getLogger(__name__)


def determine_queue_name():
    """Determine the queue name based on task pool configuration"""
    if KEEP_ARQ_TASK_POOL in [
        KEEP_ARQ_TASK_POOL_ALL,
        KEEP_ARQ_TASK_POOL_BASIC_PROCESSING,
    ]:
        return KEEP_ARQ_QUEUE_BASIC
    else:
        raise ValueError(f"Invalid task pool: {KEEP_ARQ_TASK_POOL}")


async def run_arq_worker(worker_id):
    """Run an ARQ worker"""
    logger.info(f"Starting ARQ Worker {worker_id} (PID: {os.getpid()})")

    try:
        queue_name = determine_queue_name()
    except ValueError as e:
        logger.error(str(e))
        return

    # Apply debug patches if needed
    if config("LOG_LEVEL", default="INFO") == "DEBUG":
        logger.info("Applying ARQ debug patches")
        try:
            module_name = __name__.rsplit(".", 1)[0] if "." in __name__ else ""
            import_path = (
                f"{module_name}.arq_worker_debug_patch"
                if module_name
                else "arq_worker_debug_patch"
            )

            debug_module = __import__(
                import_path, fromlist=["apply_arq_debug_patches", "patch_process_event"]
            )
            debug_module.apply_arq_debug_patches()
            debug_module.patch_process_event()
            logger.info("ARQ debug patches applied")
        except ImportError:
            logger.warning(
                "Could not import ARQ debug patches, continuing without them"
            )

    # Start the workflow manager
    logger.info("Starting Workflow Manager")
    wf_manager = WorkflowManager.get_instance()
    await wf_manager.start()
    logger.info("Workflow Manager started")

    # Get and run the ARQ worker
    worker = get_arq_worker(queue_name)
    await safe_run_worker(worker)
    logger.info(f"ARQ Worker {worker_id} finished")


class ARQWorker(SyncWorker):
    """
    Custom Gunicorn worker that runs an ARQ worker.
    This replaces the normal request handling with an ARQ worker.
    """

    def run(self):
        """
        This method is called by Gunicorn to start the worker.
        We override it to run our ARQ worker instead of handling normal requests.
        """
        logger.info(f"ARQWorker starting in process {os.getpid()}")

        # Clean up any existing DB connections
        dispose_session()

        # Get a unique worker ID
        worker_id = self.age

        try:
            # Run the ARQ worker
            asyncio.run(run_arq_worker(worker_id))
        except KeyboardInterrupt:
            logger.info(f"ARQ worker {worker_id} interrupted")
        except Exception as e:
            logger.exception(f"ARQ worker {worker_id} failed with exception: {e}")
            sys.exit(1)

        # Keep the worker alive to receive signals from Gunicorn
        while True:
            try:
                import time

                time.sleep(60)  # Sleep to keep the process alive
            except KeyboardInterrupt:
                break

    def handle_request(self, *args, **kwargs):
        """
        Handle HTTP requests - just return a simple status message.
        This is used for health checks and doesn't actually do anything.
        """
        return [b"ARQ Worker Running\n"]


def create_app():
    """
    Create a dummy WSGI app that Gunicorn will use.
    This will never actually be called in our custom worker.
    """
    logger.info("ARQ worker WSGI app created")

    # Verify task pool
    if KEEP_ARQ_TASK_POOL == KEEP_ARQ_TASK_POOL_NONE:
        logger.warning("No task pools configured to run")

    # Dummy WSGI app that just tells clients that workers are running
    def app(environ, start_response):
        data = b"ARQ Worker Running\n"
        start_response(
            "200 OK",
            [("Content-Type", "text/plain"), ("Content-Length", str(len(data)))],
        )
        return [data]

    return app


# If this module is run directly, it will act as a standalone entry point
if __name__ == "__main__":
    logger.info("Running ARQ worker standalone (without Gunicorn)")
    try:
        # Set a default worker ID for standalone execution
        worker_id = 0
        asyncio.run(run_arq_worker(worker_id))
    except KeyboardInterrupt:
        logger.info("Worker interrupted")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Worker failed with exception: {e}")
        sys.exit(1)
