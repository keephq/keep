import os

from prometheus_client import CollectorRegistry, Counter, Gauge, Summary, multiprocess

PROMETHEUS_MULTIPROC_DIR = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "/tmp/prometheus")
os.makedirs(PROMETHEUS_MULTIPROC_DIR, exist_ok=True)


# Create a single registry for all metrics
registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry, path=PROMETHEUS_MULTIPROC_DIR)

# Process event metrics
events_in_counter = Counter(
    "events_in_total", "Total number of events received", registry=registry
)
events_out_counter = Counter(
    "events_out_total", "Total number of events processed", registry=registry
)
events_error_counter = Counter(
    "events_error_total", "Total number of events with error", registry=registry
)
processing_time_summary = Summary(
    "processing_time_seconds", "Average time spent processing events", registry=registry
)

# Running tasks metrics
running_tasks_gauge = Gauge(
    "running_tasks_current",
    "Current number of running tasks",
    registry=registry,
    multiprocess_mode="livesum",
)

# Per-process running tasks metrics
running_tasks_by_process_gauge = Gauge(
    "running_tasks_by_process",
    "Current number of running tasks per process",
    labelnames=["pid"],
    registry=registry,
    multiprocess_mode="livesum",
)
