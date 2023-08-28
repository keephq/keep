import logging.config

from keep.api.core.db import push_logs_to_db


class WorkflowDBHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        # we want to push only workflow logs to the DB
        if hasattr(record, "workflow_execution_id"):
            self.records.append(record)

    def push_logs_to_db(self):
        # Convert log records to a list of dictionaries
        log_entries = [record.__dict__ for record in self.records]
        # Push log entries to the database
        push_logs_to_db(log_entries)


class WorkflowLoggerAdapter(logging.LoggerAdapter):
    def __init__(self, logger, tenant_id, workflow_id, workflow_execution_id):
        self.tenant_id = tenant_id
        self.workflow_id = workflow_id
        self.workflow_execution_id = workflow_execution_id
        super().__init__(logger, None)

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra["tenant_id"] = self.tenant_id
        extra["workflow_id"] = self.workflow_id
        extra["workflow_execution_id"] = self.workflow_execution_id
        kwargs["extra"] = extra
        return msg, kwargs

    def dump(self):
        self.logger.info("Dumping workflow logs")
        # TODO - this is a POC level code.
        # TODO - we should:
        # TODO - 1. find the right handler to push the logs to the DB
        # TODO - 2. find a better way to push the logs async (maybe another service)
        self.logger.parent.handlers[1].push_logs_to_db()
        self.logger.info("Workflow logs dumped")


CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": "%(asctime)s %(message)s %(levelname)s %(name)s %(filename)s %(otelTraceID)s %(otelSpanID)s %(otelServiceName)s",
            "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
        }
    },
    "handlers": {
        "default": {
            "level": "DEBUG",
            "formatter": "json",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "context": {
            "level": "DEBUG",
            "formatter": "json",
            "class": "keep.api.logging.WorkflowDBHandler",
        },
    },
    "loggers": {
        "": {"handlers": ["default", "context"], "level": "INFO", "propagate": False}
    },
}


def setup():
    logging.config.dictConfig(CONFIG)
