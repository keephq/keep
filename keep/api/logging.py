import copy
import inspect
import logging
import logging.config
import os

# tb: small hack to avoid the InsecureRequestWarning logs
import urllib3

from keep.api.consts import RUNNING_IN_CLOUD_RUN
from keep.api.core.db import push_logs_to_db

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class WorkflowDBHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        # we want to push only workflow logs to the DB
        if hasattr(record, "workflow_execution_id") and record.workflow_execution_id:
            self.records.append(record)

    def push_logs_to_db(self):
        # Convert log records to a list of dictionaries and clean the self.records buffer
        log_entries, self.records = [record.__dict__ for record in self.records], []
        # Push log entries to the database
        push_logs_to_db(log_entries)


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
        # add the steps/actions context
        # todo: more robust
        # added: protection from big steps context (< 64kb)
        if self.context_manager.steps_context_size < 1024 * 64:
            extra["context"] = (self.context_manager.steps_context,)
        else:
            extra["context"] = "truncated (context size > 64kb)"

        kwargs["extra"] = extra
        return msg, kwargs

    def dump(self):
        self.logger.info("Dumping workflow logs")
        # TODO - this is a POC level code.
        # TODO - we should:
        # TODO - 1. find the right handler to push the logs to the DB
        # TODO - 2. find a better way to push the logs async (maybe another service)
        workflow_db_handler = next(
            iter(
                [
                    handler
                    for handler in (
                        # tb: for some reason, when running in cloud run, the handler is nested in another handler
                        #   this needs to be handled in a better way
                        self.logger.parent.parent.handlers
                        if RUNNING_IN_CLOUD_RUN
                        else self.logger.parent.handlers
                    )
                    if isinstance(handler, WorkflowDBHandler)
                ]
            ),
            None,
        )
        if workflow_db_handler:
            workflow_db_handler.push_logs_to_db()
        else:
            self.logger.warning("No WorkflowDBHandler found")
        self.logger.info("Workflow logs dumped")


LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

LOG_FORMAT_OPEN_TELEMETRY = "open_telemetry"
LOG_FORMAT_DEVELOPMENT_TERMINAL = "dev_terminal"

LOG_FORMAT = os.environ.get("LOG_FORMAT", LOG_FORMAT_OPEN_TELEMETRY)


CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(message)s %(levelname)s %(name)s %(filename)s %(otelTraceID)s %(otelSpanID)s %(otelServiceName)s %(threadName)s %(process)s %(module)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        }
    },
    "handlers": {
        "default": {
            "level": "DEBUG",
            "formatter": "json" if LOG_FORMAT == LOG_FORMAT_OPEN_TELEMETRY else None,
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "context": {
            "level": "DEBUG",
            "formatter": "json" if LOG_FORMAT == LOG_FORMAT_OPEN_TELEMETRY else None,
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
    logging.config.dictConfig(CONFIG)
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.__class__ = CustomizedUvicornLogger
