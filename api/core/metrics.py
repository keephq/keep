import os

from prometheus_client import Counter, Gauge, Histogram, Summary

PROMETHEUS_MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus")
os.makedirs(PROMETHEUS_MULTIPROC_DIR, exist_ok=True)

METRIC_PREFIX = "keep_"

# Process event metrics
events_in_counter = Counter(
    f"{METRIC_PREFIX}events_in_total",
    "Total number of events received",
)
events_out_counter = Counter(
    f"{METRIC_PREFIX}events_processed_total",
    "Total number of events processed",
)
events_error_counter = Counter(
    f"{METRIC_PREFIX}events_error_total",
    "Total number of events with error",
)
processing_time_summary = Summary(
    f"{METRIC_PREFIX}processing_time_seconds",
    "Average time spent processing events",
)

running_tasks_gauge = Gauge(
    f"{METRIC_PREFIX}running_tasks_current",
    "Current number of running tasks",
    multiprocess_mode="livesum",
)

running_tasks_by_process_gauge = Gauge(
    f"{METRIC_PREFIX}running_tasks_by_process",
    "Current number of running tasks per process",
    labelnames=["pid"],
    multiprocess_mode="livesum",
)

### WORKFLOWS
METRIC_PREFIX = "keep_workflows_"

# Workflow execution metrics
workflow_executions_total = Counter(
    f"{METRIC_PREFIX}executions_total",
    "Total number of workflow executions",
    labelnames=["tenant_id", "workflow_id", "trigger_type"],
)

workflow_execution_errors_total = Counter(
    f"{METRIC_PREFIX}execution_errors_total",
    "Total number of workflow execution errors",
    labelnames=["tenant_id", "workflow_id", "error_type"],
)

workflow_execution_status = Counter(
    f"{METRIC_PREFIX}execution_status_total",
    "Total number of workflow executions by status",
    labelnames=["tenant_id", "workflow_id", "status"],
)

# Workflow performance metrics
workflow_execution_duration = Histogram(
    f"{METRIC_PREFIX}execution_duration_seconds",
    "Time spent executing workflows",
    labelnames=["tenant_id", "workflow_id"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),  # 1s, 5s, 10s, 30s, 1m, 2m, 5m, 10m
)

workflow_execution_step_duration = Histogram(
    f"{METRIC_PREFIX}execution_step_duration_seconds",
    "Time spent executing individual workflow steps",
    labelnames=["tenant_id", "workflow_id", "step_name"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60),
)

# Workflow state metrics
workflows_running = Gauge(
    f"{METRIC_PREFIX}running",
    "Number of currently running workflows",
    labelnames=["tenant_id"],
    multiprocess_mode="livesum",
)

workflow_queue_size = Gauge(
    f"{METRIC_PREFIX}queue_size",
    "Number of workflows waiting to be executed",
    labelnames=["tenant_id"],
    multiprocess_mode="livesum",
)
