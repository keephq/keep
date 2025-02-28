import http.client
import inspect
import logging
import logging.config
import logging.handlers
import os
import threading
import uuid
from datetime import datetime
from threading import Timer

# tb: small hack to avoid the InsecureRequestWarning logs
import urllib3
from pythonjsonlogger import jsonlogger
from sqlmodel import Session

from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.db import get_session, push_logs_to_db
from keep.api.models.db.provider import ProviderExecutionLog

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KEEP_STORE_WORKFLOW_LOGS = (
    os.environ.get("KEEP_STORE_WORKFLOW_LOGS", "true").lower() == "true"
)

logger = logging.getLogger(__name__)


class WorkflowContextFilter(logging.Filter):
    """
    This is part of the root logger configuration.

    It filters out log records that don't have a workflow_id in the thread context.
    """

    def filter(self, record):
        # Get workflow_id and debug flag from thread context
        thread = threading.current_thread()
        workflow_id = getattr(thread, "workflow_id", None)

        # Early return if no workflow_id
        if not workflow_id:
            return False

        # Skip DEBUG logs unless debug mode is enabled
        if not getattr(thread, "workflow_debug", False) and record.levelname == "DEBUG":
            return False

        # Initialize record.extra if needed
        if not hasattr(record, "extra"):
            record.extra = {}

        # Get thread context attributes
        thread_attrs = {
            "workflow_id": workflow_id,
            "workflow_execution_id": getattr(thread, "workflow_execution_id", None),
            "tenant_id": getattr(thread, "tenant_id", None),
            "provider_type": getattr(thread, "provider_type", None),
        }

        # Set record attributes from thread context
        for attr, value in thread_attrs.items():
            if value is not None:
                setattr(record, attr, value)

        # Handle step_id
        step_id = getattr(thread, "step_id", None)
        if step_id is not None:
            record.context = {"step_id": step_id}

        # Handle event if present
        if "event" in record.__dict__:
            if hasattr(record, "context"):
                record.context["event"] = record.event
            else:
                record.context = {"event": record.event}

        return True


class WorkflowDBHandler(logging.Handler):
    def __init__(self, flush_interval: int = 2):
        super().__init__()
        logging.getLogger(__name__).info("Initializing WorkflowDBHandler")
        self.records = []
        self.flush_interval = flush_interval
        self._stop_event = threading.Event()
        # Start repeating timer in a separate thread
        self._timer_thread = threading.Thread(target=self._timer_run)
        self._timer_thread.daemon = (
            True  # Make it a daemon so it stops when program exits
        )
        logging.getLogger(__name__).info("Starting WorkflowDBHandler timer thread")
        self._timer_thread.start()
        logging.getLogger(__name__).info("Started WorkflowDBHandler timer thread")

    def _timer_run(self):
        while not self._stop_event.is_set():
            # logging.getLogger(__name__).info("Timer running")
            self.flush()
            # logging.getLogger(__name__).info("Timer sleeping")
            self._stop_event.wait(self.flush_interval)  # Wait but can be interrupted

    def close(self):
        self._stop_event.set()  # Signal the timer to stop
        self._timer_thread.join()  # Wait for timer thread to finish
        super().close()

    def emit(self, record):
        # we want to push only workflow logs to the DB
        if not KEEP_STORE_WORKFLOW_LOGS:
            return
        if hasattr(record, "workflow_execution_id") and record.workflow_execution_id:
            self.format(record)
            self.records.append(record)

    def push_logs_to_db(self):
        # Convert log records to a list of dictionaries and clean the self.records buffer
        log_entries, self.records = [record.__dict__ for record in self.records], []
        # Push log entries to the database
        push_logs_to_db(log_entries)

    def flush(self):
        if not self.records:
            return

        try:
            logging.getLogger(__name__).info("Flushing workflow logs to DB")
            self.push_logs_to_db()
            logging.getLogger(__name__).info("Flushed workflow logs to DB")
        except Exception as e:
            # Use the parent logger to avoid infinite recursion
            logging.getLogger(__name__).error(
                f"Failed to flush workflow logs: {str(e)}"
            )
        finally:
            # Clear the timer reference
            self._flush_timer = None


class ProviderDBHandler(logging.Handler):
    def __init__(self, flush_interval: int = 2):
        super().__init__()
        self.records = []
        self.flush_interval = flush_interval
        self._flush_timer = None

    def emit(self, record):
        # Only store provider logs
        if hasattr(record, "provider_id") and record.provider_id:
            self.records.append(record)

            # Cancel existing timer if any
            if self._flush_timer:
                self._flush_timer.cancel()

            # Start new timer
            self._flush_timer = Timer(self.flush_interval, self.flush)
            self._flush_timer.start()

    def flush(self):
        if not self.records:
            return

        # Copy records and clear original list to avoid race conditions
        _records = self.records.copy()
        self.records = []

        try:
            session = Session(next(get_session()).bind)
            log_entries = []

            for record in _records:
                # if record have execution_id use it, but mostly for future use
                if hasattr(record, "execution_id"):
                    execution_id = record.execution_id
                else:
                    execution_id = None
                entry = ProviderExecutionLog(
                    id=str(uuid.uuid4()),
                    tenant_id=record.tenant_id,
                    provider_id=record.provider_id,
                    timestamp=datetime.fromtimestamp(record.created),
                    log_message=record.getMessage(),
                    log_level=record.levelname,
                    context=getattr(record, "extra", {}),
                    execution_id=execution_id,
                )
                log_entries.append(entry)

            session.add_all(log_entries)
            session.commit()
            session.close()
        except Exception as e:
            # Use the parent logger to avoid infinite recursion
            logging.getLogger(__name__).error(
                f"Failed to flush provider logs: {str(e)}"
            )
        finally:
            # Clear the timer reference
            self._flush_timer = None

    def close(self):
        """Cancel timer and flush remaining logs when handler is closed"""
        if self._flush_timer:
            self._flush_timer.cancel()
            self._flush_timer = None
        self.flush()
        super().close()


class ProviderLoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger, provider_instance, tenant_id, provider_id, step_id=None):
        # Create a new logger specifically for this adapter
        self.provider_logger = logging.getLogger(f"provider.{provider_id}")

        # Add the ProviderDBHandler only to this specific logger
        handler = ProviderDBHandler()
        self.provider_logger.addHandler(handler)

        # Initialize the adapter with the new logger
        super().__init__(self.provider_logger, {})
        self.provider_instance = provider_instance
        self.tenant_id = tenant_id
        self.provider_id = provider_id
        self.execution_id = str(uuid.uuid4())
        self.step_id = step_id

    def process(self, msg, kwargs):
        kwargs = kwargs.copy() if kwargs else {}
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        kwargs["extra"].update(
            {
                "tenant_id": self.tenant_id,
                "provider_id": self.provider_id,
                "execution_id": self.execution_id,
            }
        )

        return msg, kwargs


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
KEEP_LOG_FILE = os.environ.get("KEEP_LOG_FILE")

LOG_FORMAT_OPEN_TELEMETRY = "open_telemetry"
LOG_FORMAT_DEVELOPMENT_TERMINAL = "dev_terminal"

LOG_FORMAT = os.environ.get("LOG_FORMAT", LOG_FORMAT_OPEN_TELEMETRY)


class DevTerminalFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, "otelTraceID"):
            record.otelTraceID = "-"  # or any default value you prefer

        message = super().format(record)
        extra_info = ""

        # Use inspect to go up the stack until we find the _log function
        frame = inspect.currentframe()
        while frame:
            if frame.f_code.co_name == "_log":
                # Extract extra from the _log function's local variables
                extra = frame.f_locals.get("extra", {})
                if extra:
                    extra_info = " ".join(
                        [f"[{k}: {v}]" for k, v in extra.items() if k != "raw_event"]
                    )
                else:
                    extra_info = ""
                break
            frame = frame.f_back

        return f"{message} {extra_info}"


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def __init__(self, *args, rename_fields=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rename_fields = rename_fields if RUNNING_IN_CLOUD_RUN else {}


CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": CustomJsonFormatter,
            "fmt": "%(asctime)s %(message)s %(levelname)s %(name)s %(filename)s %(otelTraceID)s %(otelSpanID)s %(otelTraceSampled)s %(otelServiceName)s %(threadName)s %(process)s %(module)s",
            "rename_fields": {
                "levelname": "severity",
                "asctime": "timestamp",
                "otelTraceID": "logging.googleapis.com/trace",
                "otelSpanID": "logging.googleapis.com/spanId",
                "otelTraceSampled": "logging.googleapis.com/trace_sampled",
            },
        },
        "dev_terminal": {
            "()": DevTerminalFormatter,
            "format": "%(asctime)s - %(thread)s %(otelTraceID)s %(threadName)s %(levelname)s - %(message)s",
        },
        "uvicorn_access": {  # Add new formatter for uvicorn.access
            "format": "%(asctime)s - %(otelTraceID)s - %(threadName)s - %(message)s"
        },
    },
    "handlers": {
        "default": {
            "level": LOG_LEVEL,
            "formatter": (
                "json" if LOG_FORMAT == LOG_FORMAT_OPEN_TELEMETRY else "dev_terminal"
            ),
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "workflowhandler": {
            "level": "DEBUG",
            "formatter": (
                "json" if LOG_FORMAT == LOG_FORMAT_OPEN_TELEMETRY else "dev_terminal"
            ),
            "class": "keep.api.logging.WorkflowDBHandler",
            "filters": ["thread_context"],  # Add filter here
        },
        "uvicorn_access": {  # Add new handler for uvicorn.access
            "class": "logging.StreamHandler",
            "formatter": "uvicorn_access",
        },
    },
    "filters": {  # Add filters section
        "thread_context": {"()": "keep.api.logging.WorkflowContextFilter"}
    },
    "loggers": {
        "": {
            "handlers": ["workflowhandler", "default"],
            "level": "DEBUG",
            "propagate": False,
        },
        "slowapi": {
            "handlers": ["default"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "uvicorn.access": {  # Add uvicorn.access logger configuration
            "handlers": ["uvicorn_access"],
            "level": "INFO",
            "propagate": False,
        },
        "uvicorn.error": {  # Add uvicorn.error logger configuration
            "()": "CustomizedUvicornLogger",  # Use custom logger class
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
        "opentelemetry.context": {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
        "Evaluator": {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
        "NameContainer": {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
        "evaluation": {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
        "Environment": {
            "handlers": [],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}


class CustomizedUvicornLogger(logging.Logger):
    """This class overrides the default Uvicorn logger to add trace_id to the log record

    Args:
        logging (_type_): _description_
    """

    def makeRecord(
        self,
        name,
        level,
        fn,
        lno,
        msg,
        args,
        exc_info,
        func=None,
        extra=None,
        sinfo=None,
    ):
        if extra:
            trace_id = extra.pop("otelTraceID", None)
        else:
            trace_id = None
        rv = super().makeRecord(
            name, level, fn, lno, msg, args, exc_info, func, extra, sinfo
        )
        if trace_id:
            rv.__dict__["otelTraceID"] = trace_id
        return rv

    def _log(
        self,
        level,
        msg,
        args,
        exc_info=None,
        extra=None,
        stack_info=False,
        stacklevel=1,
    ):
        # Find trace_id from call stack
        frame = (
            inspect.currentframe().f_back
        )  # Go one level up to get the caller's frame
        while frame:
            found_frame = False
            if frame.f_code.co_name == "run_asgi":
                trace_id = (
                    frame.f_locals.get("self").scope.get("state", {}).get("trace_id", 0)
                )
                tenant_id = (
                    frame.f_locals.get("self")
                    .scope.get("state", {})
                    .get("tenant_id", 0)
                )
                if trace_id:
                    if extra is None:
                        extra = {}
                    extra.update({"otelTraceID": trace_id})
                    found_frame = True
                if tenant_id:
                    if extra is None:
                        extra = {}
                    extra.update({"tenant_id": tenant_id})
                    found_frame = True
            # if we found the frame, we can stop searching
            if found_frame:
                break
            frame = frame.f_back

        # Call the original _log function to handle the logging with trace_id
        logging.Logger._log(
            self, level, msg, args, exc_info, extra, stack_info, stacklevel
        )


def setup_logging():
    # Add file handler if KEEP_LOG_FILE is set
    if KEEP_LOG_FILE:
        CONFIG["handlers"]["file"] = {
            "level": "DEBUG",
            "formatter": ("json"),
            "class": "logging.FileHandler",
            "filename": KEEP_LOG_FILE,
            "mode": "a",
        }
        # Add file handler to root logger
        CONFIG["loggers"][""]["handlers"].append("file")

    logging.config.dictConfig(CONFIG)
    # MONKEY PATCHING http.client
    # See: https://stackoverflow.com/questions/58738195/python-http-request-and-debug-level-logging-to-the-log-file
    http_client_logger = logging.getLogger("http.client")
    http_client_logger.setLevel(logging.DEBUG)
    http.client.HTTPConnection.debuglevel = 1

    def print_to_log(*args):
        http_client_logger.debug(" ".join(args))

    # monkey-patch a `print` global into the http.client module; all calls to
    # print() in that module will then use our print_to_log implementation
    http.client.print = print_to_log
