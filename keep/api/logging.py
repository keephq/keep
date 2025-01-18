import copy
import inspect
import logging
import logging.config
import os
import uuid
from datetime import datetime
from threading import Timer

# tb: small hack to avoid the InsecureRequestWarning logs
import urllib3
from sqlmodel import Session

from keep.api.core.db import get_session, push_logs_to_db
from keep.api.models.db.provider import ProviderExecutionLog

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

KEEP_STORE_WORKFLOW_LOGS = (
    os.environ.get("KEEP_STORE_WORKFLOW_LOGS", "true").lower() == "true"
)


class WorkflowDBHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        # we want to push only workflow logs to the DB
        if not KEEP_STORE_WORKFLOW_LOGS:
            return
        if hasattr(record, "workflow_execution_id") and record.workflow_execution_id:
            self.records.append(record)

    def push_logs_to_db(self):
        # Convert log records to a list of dictionaries and clean the self.records buffer
        log_entries, self.records = [record.__dict__ for record in self.records], []
        # Push log entries to the database
        push_logs_to_db(log_entries)


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


class WorkflowLoggerAdapter(logging.LoggerAdapter):
    def __init__(
        self, logger, context_manager, tenant_id, workflow_id, workflow_execution_id
    ):
        self.tenant_id = tenant_id
        self.workflow_id = workflow_id
        self.workflow_execution_id = workflow_execution_id
        self.context_manager = context_manager
        super().__init__(logger, None)

    def process(self, msg, kwargs):
        extra = copy.deepcopy(kwargs.get("extra", {}))
        extra["tenant_id"] = self.tenant_id
        extra["workflow_id"] = self.workflow_id
        extra["workflow_execution_id"] = self.workflow_execution_id

        step_id = extra.pop("step_id", None)
        if step_id:
            # everything added to 'context', will be saved in the db column 'context' and is used by frontend. Feel free to add more context here
            extra["context"] = {"step_id": step_id}

        kwargs["extra"] = extra
        return msg, kwargs

    def dump(self):
        self.logger.info("Dumping workflow logs")
        root_logger = logging.getLogger()
        handlers = root_logger.handlers
        workflow_db_handler = None

        for handler in handlers:
            # should be always the second
            if isinstance(handler, WorkflowDBHandler):
                workflow_db_handler = handler
                break

        if workflow_db_handler:
            self.logger.info("Pushing logs to DB")
            workflow_db_handler.push_logs_to_db()
        else:
            self.logger.warning("No WorkflowDBHandler found")
        self.logger.info("Workflow logs dumped")


class ProviderLoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger, provider_instance, tenant_id, provider_id):
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


CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(message)s %(levelname)s %(name)s %(filename)s %(otelTraceID)s %(otelSpanID)s %(otelServiceName)s %(threadName)s %(process)s %(module)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        },
        "dev_terminal": {
            "()": DevTerminalFormatter,
            "format": "%(asctime)s - %(thread)s %(threadName)s %(levelname)s - %(message)s",
        },
    },
    "handlers": {
        "default": {
            "level": "DEBUG",
            "formatter": (
                "json" if LOG_FORMAT == LOG_FORMAT_OPEN_TELEMETRY else "dev_terminal"
            ),
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "context": {
            "level": "DEBUG",
            "formatter": (
                "json" if LOG_FORMAT == LOG_FORMAT_OPEN_TELEMETRY else "dev_terminal"
            ),
            "class": "keep.api.logging.WorkflowDBHandler",
        },
    },
    "loggers": {
        "": {
            "handlers": ["default", "context"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        # shut the open telemetry logger down since it keep pprints  <Token var=<ContextVar name='current_context' default={} at was created in a different Context
        #       https://github.com/open-telemetry/opentelemetry-python/issues/2606
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
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.__class__ = CustomizedUvicornLogger

    # ADJUST UVICORN ACCESS LOGGER
    # https://github.com/benoitc/gunicorn/issues/2299
    # https://github.com/benoitc/gunicorn/issues/2382
    LOG_FMT = "%(asctime)s - %(otelTraceID)s - %(threadName)s - %(message)s"
    logger = logging.getLogger("uvicorn.access")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FMT))
    logger.handlers = [handler]
