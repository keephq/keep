import os
import uuid
import posthog
import requests
from posthog import Posthog
from importlib import metadata

from keep.api.core.db import get_or_creat_posthog_instance_id

try:
    KEEP_VERSION = metadata.version("keep")
except metadata.PackageNotFoundError:
    try:
        KEEP_VERSION = metadata.version("keephq")
    except metadata.PackageNotFoundError:
        KEEP_VERSION = os.environ.get("KEEP_VERSION", "unknown")

POSTHOG_DISABLED = os.getenv("POSTHOG_DISABLED", "false") == "true"

if POSTHOG_DISABLED:
    posthog.disabled = True

POSTHOG_API_KEY = (
    os.getenv("POSTHOG_API_KEY")
    or "phc_muk9qE3TfZsX3SZ9XxX52kCGJBclrjhkP9JxAQcm1PZ"  # It's a public PH API key, not a leaked secret ;)
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
            get_or_creat_posthog_instance_id(), 
            "connectivity_check",
        )
        return True
    except requests.exceptions.ConnectionError:
        return False
