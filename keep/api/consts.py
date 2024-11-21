import os

from dotenv import find_dotenv, load_dotenv

from keep.api.models.db.preset import PresetDto, StaticPresetsId

load_dotenv(find_dotenv())
RUNNING_IN_CLOUD_RUN = os.environ.get("K_SERVICE") is not None
PROVIDER_PULL_INTERVAL_DAYS = int(
    os.environ.get("KEEP_PULL_INTERVAL", 7)
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

###
# Set ARQ_TASK_POOL_TO_EXECUTE to "none", "all", "basic_processing" or "ai"
# to split the tasks between the workers.
###

KEEP_ARQ_TASK_POOL_NONE = "none"  # Arq workers explicitly disabled for this service
KEEP_ARQ_TASK_POOL_ALL = "all"  # All arq workers enabled for this service
KEEP_ARQ_TASK_POOL_BASIC_PROCESSING = "basic_processing"  # Everything except AI
# Define queues for different task types
KEEP_ARQ_QUEUE_BASIC = "basic_processing"

REDIS = os.environ.get("REDIS", "false") == "true"
KEEP_ARQ_TASK_POOL = os.environ.get("KEEP_ARQ_TASK_POOL", None)

if KEEP_ARQ_TASK_POOL is None:
    if REDIS:
        KEEP_ARQ_TASK_POOL = KEEP_ARQ_TASK_POOL_ALL
    else:
        KEEP_ARQ_TASK_POOL = KEEP_ARQ_TASK_POOL_NONE

if KEEP_ARQ_TASK_POOL != KEEP_ARQ_TASK_POOL_NONE and not REDIS:
    raise Exception("Starting the ARQ worker, but REDIS is not enabled.")
