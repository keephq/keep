import os
import uuid
import posthog
import requests
from posthog import Posthog
from importlib import metadata

try:
    KEEP_VERSION = metadata.version("keep")
except metadata.PackageNotFoundError:
    try:
        KEEP_VERSION = metadata.version("keephq")
    except metadata.PackageNotFoundError:
        KEEP_VERSION = os.environ.get("KEEP_VERSION", "unknown")

POSTHOG_DISABLED = os.getenv("POSTHOG_DISABLED", "false") == "true"
RANDOM_TENANT_ID_PERSISTENT_WITHIN_LAUNCH = uuid.uuid4()

if POSTHOG_DISABLED:
    posthog.disabled = True

POSTHOG_API_KEY = (
    os.getenv("POSTHOG_API_KEY")
    or "phc_muk9qE3TfZsX3SZ9XxX52kCGJBclrjhkP9JxAQcm1PZ"
)
posthog_client = Posthog(
    api_key=POSTHOG_API_KEY, 
    host="https://app.posthog.com", 
)


def is_posthog_reachable():
    try:
        Posthog(
            api_key=POSTHOG_API_KEY, 
            host="https://app.posthog.com", 
            feature_flags_request_timeout_seconds=3,
            sync_mode=True  # Explicitly to trigger exception if it's not reachable.
        ).capture(
            RANDOM_TENANT_ID_PERSISTENT_WITHIN_LAUNCH, 
            "connectivity_check",
        )
        return True
    except requests.exceptions.ConnectionError:
        return False
