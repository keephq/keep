"""
Prometheus metrics (multiprocess-safe).

Key rules in multiprocess mode:
- DO NOT use Summary (unsupported / corrupt in multiproc). Use Histogram.
- PROMETHEUS_MULTIPROC_DIR must be cleaned on master start, not per-worker.
- Use multiprocess.MultiProcessCollector in your /metrics endpoint.
- Watch label cardinality like it owes you money.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
from typing import Optional

from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# ----------------------------
# Multiprocess setup
# ----------------------------

PROMETHEUS_MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus")

# If you're running gunicorn, the master has no worker id.
# Workers will have GUNICORN_WORKER_ID.
_GUNICORN_WORKER_ID = os.environ.get("GUNICORN_WORKER_ID")

# allow disabling cleanup if your runtime already does it
CLEANUP_ENABLED = os.environ.get("PROMETHEUS_MULTIPROC_CLEANUP", "true").lower() == "true"


def _is_master_process() -> bool:
    """
    Best-effort master detection:
    - gunicorn: master has no GUNICORN_WORKER_ID
    - otherwise: user can force cleanup (dangerous) or disable it
    """
    if _GUNICORN_WORKER_ID is not None:
        return False
    # If not under gunicorn, treat as "master-like" only if explicitly allowed.
    # Otherwise you risk every uvicorn worker wiping the dir.
    return os.environ.get("PROMETHEUS_ASSUME_MASTER", "false").lower() == "true"


def _init_multiproc_dir() -> None:
    # Always ensure directory exists
    os.makedirs(PROMETHEUS_MULTIPROC_DIR, exist_ok=True)

    if not CLEANUP_ENABLED:
        logger.info("PROMETHEUS_MULTIPROC_DIR cleanup disabled")
        return

    if not _is_master_process():
        # Workers must never wipe the directory.
        return

    try:
        if os.path.exists(PROMETHEUS_MULTIPROC_DIR):
            shutil.rmtree(PROMETHEUS_MULTIPROC_DIR)
        os.makedirs(PROMETHEUS_MULTIPROC_DIR, exist_ok=True)
        logger.info("Cleaned PROMETHEUS_MULTIPROC_DIR=%s", PROMETHEUS_MULTIPROC_DIR)
    except Exception:
        logger.exception("Failed to clean PROMETHEUS_MULTIPROC_DIR=%s", PROMETHEUS_MULTIPROC_DIR)


_init_multiproc_dir()

# ----------------------------
# Label safety helpers
# ----------------------------

# If you insist on workflow_id being a UUID label, you're choosing pain.
# At minimum, you can bucket/harden it, or disable it entirely with env toggles.
ALLOW_WORKFLOW_ID_LABEL = os.environ.get("PROMETHEUS_ALLOW_WORKFLOW_ID_LABEL", "false").lower() == "true"

# Hard cap label length to prevent accidental megabyte labels.
_MAX_LABEL_LEN = int(os.environ.get("PROMETHEUS_MAX_LABEL_LEN", "80"))

_SAFE_LABEL_RE = re.compile(r"[^a-zA-Z0-9:_\-.]")


def _safe_label(value: Optional[str]) -> str:
    if value is None:
        return "unknown"
    v = str(value).strip()
    v = _SAFE_LABEL_RE.sub("_", v)
    if len(v) > _MAX_LABEL_LEN:
        v = v[:_MAX_LABEL_LEN]
    return v


def workflow_label(workflow_id: Optional[str]) -> str:
    """
    If workflow_id label is disabled, collapse everything into a single bucket.
    This avoids cardinality explosions (which are real and ugly).
    """
    if not ALLOW_WORKFLOW_ID_LABEL:
        return "all"
    return _safe_label(workflow_id)


# ----------------------------
# Metrics
# ----------------------------

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

# CRITICAL FIX: Summary is not supported in multiprocess mode.
processing_time_histogram = Histogram(
    f"{METRIC_PREFIX}processing_time_seconds",
    "Time spent processing events",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

running_tasks_gauge = Gauge(
    f"{METRIC_PREFIX}running_tasks_current",
    "Current number of running tasks (global)",
    multiprocess_mode="livesum",
)

# PID labeled metrics: do NOT livesum, it’s redundant and can mislead.
running_tasks_by_process_gauge = Gauge(
    f"{METRIC_PREFIX}running_tasks_by_process",
    "Current number of running tasks per process",
    labelnames=["pid"],
    multiprocess_mode="all",
)

# ----------------------------
# Workflow metrics
# ----------------------------

WF_PREFIX = "keep_workflows_"

# WARNING: tenant_id + workflow_id can explode cardinality.
# If workflow_id is UUID-like, keep PROMETHEUS_ALLOW_WORKFLOW_ID_LABEL=false unless you enjoy pain.

workflow_executions_total = Counter(
    f"{WF_PREFIX}executions_total",
    "Total number of workflow executions",
    labelnames=["tenant_id", "workflow_id", "trigger_type"],
)

workflow_execution_errors_total = Counter(
    f"{WF_PREFIX}execution_errors_total",
    "Total number of workflow execution errors",
    labelnames=["tenant_id", "workflow_id", "error_type"],
)

workflow_execution_status = Counter(
    f"{WF_PREFIX}execution_status_total",
    "Total number of workflow executions by status",
    labelnames=["tenant_id", "workflow_id", "status"],
)

workflow_execution_duration = Histogram(
    f"{WF_PREFIX}execution_duration_seconds",
    "Time spent executing workflows",
    labelnames=["tenant_id", "workflow_id"],
    buckets=(1, 2, 5, 10, 30, 60, 120, 300, 600),
)

workflow_execution_step_duration = Histogram(
    f"{WF_PREFIX}execution_step_duration_seconds",
    "Time spent executing individual workflow steps",
    labelnames=["tenant_id", "workflow_id", "step_name"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

workflows_running = Gauge(
    f"{WF_PREFIX}running",
    "Number of currently running workflows",
    labelnames=["tenant_id"],
    multiprocess_mode="livesum",
)

workflow_queue_size = Gauge(
    f"{WF_PREFIX}queue_size",
    "Number of workflows waiting to be executed",
    labelnames=["tenant_id"],
    multiprocess_mode="livesum",
)