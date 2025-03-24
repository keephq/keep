import asyncio
import logging
import os
import signal
import sys
import threading
import time

from dotenv import find_dotenv, load_dotenv
from gunicorn.workers.base import Worker

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


async def run_arq_worker(worker_id, number_of_errors_before_restart=0):
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
    try:
        await safe_run_worker(
            worker, number_of_errors_before_restart=number_of_errors_before_restart
        )
    except Exception as e:
        logger.exception(f"ARQ worker failed: {e}")
        # let GUnicorn restart the worker
        os._exit(1)
    logger.info(f"ARQ Worker {worker_id} finished")


class ARQGunicornWorker(Worker):
    """
    Custom Gunicorn worker that runs an ARQ worker.
    This worker properly integrates with Gunicorn's request handling model.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the worker"""
        super().__init__(*args, **kwargs)
        self.worker_id = self.age
        self.arq_running = False
        self.loop = None
        self.heartbeat_file = None
        self.last_heartbeat = 0
        self.stop_heartbeat = False
        self.heartbeat_thread = None
        self.logger = logging.getLogger(__name__)
        self.number_of_errors_before_restart = config(
            "ARQ_NUMBER_OF_ERRORS_BEFORE_RESTART", cast=int, default=5
        )

        # Setup heartbeat directory
        self.heartbeat_dir = os.environ.get("ARQ_HEARTBEAT_DIR", "/tmp/arq_heartbeats")
        os.makedirs(self.heartbeat_dir, exist_ok=True)

        # Initialize heartbeat file
        self.heartbeat_file = os.path.join(
            self.heartbeat_dir, f"arq_worker_{os.getpid()}.heartbeat"
        )
        self.max_heartbeat_age = int(os.environ.get("ARQ_MAX_HEARTBEAT_AGE", "30"))

        # Store ARQ task
        self.arq_task = None

    def update_heartbeat(self):
        """Update the heartbeat file to indicate the worker is alive"""
        try:
            self.logger.info(f"Updating heartbeat: {self.heartbeat_file}")
            self.last_heartbeat = time.time()
            with open(self.heartbeat_file, "w") as f:
                f.write(str(self.last_heartbeat))
        except Exception as e:
            self.logger.warning(f"Failed to update heartbeat: {e}")

    def start_heartbeat_thread(self):
        """Start a background thread to update the heartbeat file"""
        self.stop_heartbeat = False

        def heartbeat_loop():
            """Periodic heartbeat updates"""
            while not self.stop_heartbeat:
                self.update_heartbeat()
                time.sleep(5)  # Update heartbeat every 5 seconds

        self.logger.info("Starting heartbeat thread")
        self.heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()

    def check_heartbeat(self):
        """Check if heartbeat is still being updated, return True if healthy"""
        try:
            if os.path.exists(self.heartbeat_file):
                with open(self.heartbeat_file, "r") as f:
                    try:
                        last_heartbeat = float(f.read().strip())
                        # Check if heartbeat is too old
                        heartbeat_age = time.time() - last_heartbeat
                        if heartbeat_age > self.max_heartbeat_age:
                            self.log.error(
                                f"Heartbeat is too old: {heartbeat_age:.1f}s > {self.max_heartbeat_age}s"
                            )
                            return False
                        return True
                    except ValueError:
                        self.log.error("Invalid heartbeat value")
                        return False
            else:
                self.log.error(f"Heartbeat file not found: {self.heartbeat_file}")
                return False
        except Exception as e:
            self.log.exception(f"Error checking heartbeat: {e}")
            return False

    async def handle_http_request(self, reader, writer):
        """Handle HTTP health check requests"""
        try:
            # Read the request (but we don't really care about the content)
            # We just need to read enough to clear the buffer
            await reader.read(1024)

            # Check worker health
            if self.check_heartbeat() and self.arq_running:
                response = f"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n\r\nARQ Worker {self.worker_id} Running\n"
            else:
                response = f"HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/plain\r\n\r\nARQ Worker {self.worker_id} Heartbeat Failed\n"

            # Send the response
            writer.write(response.encode())
            await writer.drain()

        except Exception as e:
            self.log.exception(f"Error handling HTTP request: {e}")
            try:
                error_response = "HTTP/1.1 500 Internal Server Error\r\nContent-Type: text/plain\r\n\r\nError processing request\n"
                writer.write(error_response.encode())
                await writer.drain()
            except Exception as e:
                pass
        finally:
            # Close the connection
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _run(self):
        """Run the ARQ worker and handle requests from Gunicorn"""
        self.log.info(f"Starting ARQ worker {self.worker_id} in process {os.getpid()}")

        # Start the ARQ worker
        self.arq_running = True
        self.arq_task = asyncio.create_task(
            run_arq_worker(
                self.worker_id,
                number_of_errors_before_restart=self.number_of_errors_before_restart,
            )
        )

        # Wait for the ARQ worker to complete
        try:
            await self.arq_task
        except Exception as e:
            self.log.exception(f"ARQ worker failed: {e}")
            # let GUnicorn restart the worker
            os._exit(1)
        finally:
            self.arq_running = False
            self.log.info(f"ARQ worker {self.worker_id} finished")

    def init_process(self):
        """Initialize the worker process - required Gunicorn Worker method"""

        # Start heartbeat
        self.update_heartbeat()
        self.start_heartbeat_thread()

        self.logger.info("Init process")
        # Initialize the base worker
        super().init_process()

        # Clean up any existing DB connections
        dispose_session()

    def run(self):
        """Run the worker - required Gunicorn Worker method"""
        self.log.info(f"ARQGunicornWorker running in process {os.getpid()}")

        # Create and set the event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Set up signal handlers in the main thread
        for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGQUIT]:
            self.loop.add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(self.handle_signal(s))
            )

        # Run the ARQ worker
        try:
            self.arq_task = self.loop.create_task(self._run())

            # This is the key part: we use Gunicorn's socket to handle requests
            # The sockets are already set up by Gunicorn's master process
            for sock in self.sockets:
                # Create server for each socket passed by Gunicorn
                server = asyncio.start_server(
                    self.handle_http_request,
                    sock=sock,
                )
                self.loop.run_until_complete(server)
                self.log.info(f"Started HTTP server on socket {sock}")

            # Run the event loop
            self.loop.run_forever()

        except Exception as e:
            self.log.exception(f"Error in main event loop: {e}")
        finally:
            self.logger.info("Shutting down ARQGunicornWorker")
            self.stop_heartbeat = True
            if self.heartbeat_thread and self.heartbeat_thread.is_alive():
                self.heartbeat_thread.join(timeout=5)
                self.logger.info("Heartbeat thread stopped")

            # Clean up the event loop
            try:
                # Cancel any pending tasks
                for task in asyncio.all_tasks(self.loop):
                    task.cancel()

                # Run the loop until tasks are cancelled
                self.loop.run_until_complete(asyncio.sleep(0.1))

                # Close the loop
                self.loop.close()
            except Exception as e:
                self.log.exception(f"Error closing event loop: {e}")

    async def handle_signal(self, sig):
        """Handle signals asynchronously"""
        self.log.info(f"Received signal {sig}, shutting down")
        self.arq_running = False

        # Cancel the ARQ task if it's running
        if self.arq_task and not self.arq_task.done():
            self.arq_task.cancel()
            try:
                await self.arq_task
            except asyncio.CancelledError:
                self.log.info("ARQ task cancelled")

        # Stop the event loop
        self.loop.stop()


def create_app():
    """
    Create a simple WSGI app for Gunicorn.
    This is just a placeholder as our custom worker handles all the logic.
    """
    logger.info("Creating ARQ worker WSGI app")

    # Verify task pool
    if KEEP_ARQ_TASK_POOL == KEEP_ARQ_TASK_POOL_NONE:
        logger.warning("No task pools configured to run")

    # Simple WSGI app that just returns a status message
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
