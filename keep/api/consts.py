import os

from dotenv import find_dotenv, load_dotenv

from keep.api.models.db.preset import PresetDto, StaticPresetsId

load_dotenv(find_dotenv())
RUNNING_IN_CLOUD_RUN = os.environ.get("K_SERVICE") is not None
PROVIDER_PULL_INTERVAL_MINUTE = int(
    os.environ.get("KEEP_PULL_INTERVAL", 10080)
)  # maximum once a week
STATIC_PRESETS = {
    "feed": PresetDto(
        id=StaticPresetsId.FEED_PRESET_ID.value,
        name="feed",
        options=[
            {"label": "CEL", "value": ""},
            {
                "label": "SQL",
                "value": {"sql": "", "params": {}},
            },
        ],
        created_by=None,
        is_private=False,
        is_noisy=False,
        should_do_noise_now=False,
        static=True,
        tags=[],
    )
}
MAINTENANCE_WINDOW_ALERT_STRATEGY = os.environ.get(
    "MAINTENANCE_WINDOW_STRATEGY", "default"
)  # recover_previous_status or default
WATCHER_LAPSED_TIME = int(os.environ.get("KEEP_WATCHER_LAPSED_TIME", 60))  # in seconds
###
# Set ARQ_TASK_POOL_TO_EXECUTE to "none", "all", "basic_processing" or "ai"
# to split the tasks between the workers.
###

KEEP_ARQ_TASK_POOL_ALL = "all"  # All arq workers enabled for this service
KEEP_ARQ_TASK_POOL_BASIC_PROCESSING = "basic_processing"  # Everything except AI
# Define queues for different task types
KEEP_ARQ_QUEUE_BASIC = "basic_processing"
KEEP_ARQ_QUEUE_WORKFLOWS = "workflows"
KEEP_ARQ_QUEUE_MAINTENANCE = "maintenance"

REDIS = os.environ.get("REDIS", "false") == "true"

if REDIS:
    KEEP_ARQ_TASK_POOL = os.environ.get("KEEP_ARQ_TASK_POOL", KEEP_ARQ_TASK_POOL_ALL)
else:
    KEEP_ARQ_TASK_POOL = os.environ.get("KEEP_ARQ_TASK_POOL", None)

OPENAI_MODEL_NAME = os.environ.get("OPENAI_MODEL_NAME", "gpt-4o-2024-08-06")

KEEP_CORRELATION_ENABLED = os.environ.get("KEEP_CORRELATION_ENABLED", "true") == "true"

FINGERPRINT_PAYLOAD_LIMIT = 100


def fingerprints_for_poll_payload(fingerprints: list[str]) -> list[str]:
    if len(fingerprints) <= FINGERPRINT_PAYLOAD_LIMIT:
        return fingerprints
    return []


def poll_alerts_payload(
    fingerprints: list[str],
    alert_transitions: list[dict] | None = None,
) -> dict:
    """Build the poll-alerts Pusher payload with optional status-transition metadata.

    Args:
        fingerprints: List of alert fingerprints that changed.
        alert_transitions: Optional list of dicts with keys:
            fingerprint, status, previous_status.

    Returns:
        A dict suitable for Pusher trigger. If over FINGERPRINT_PAYLOAD_LIMIT,
        returns {"fingerprints": []} and omits transition fields.
    """
    if len(fingerprints) > FINGERPRINT_PAYLOAD_LIMIT:
        return {"fingerprints": []}

    payload: dict = {"fingerprints": fingerprints}

    if alert_transitions is not None:
        payload["alerts"] = alert_transitions
        payload["statuses"] = {
            t["fingerprint"]: t["status"] for t in alert_transitions
        }
        payload["resolved_fingerprints"] = [
            t["fingerprint"]
            for t in alert_transitions
            if t["status"] == "resolved"
        ]

    return payload
