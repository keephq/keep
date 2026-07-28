import os
from importlib import metadata

from keep.api.core.db import get_or_creat_posthog_instance_id

try:
    KEEP_VERSION = metadata.version("keep")
except metadata.PackageNotFoundError:
    try:
        KEEP_VERSION = metadata.version("keephq")
    except metadata.PackageNotFoundError:
        KEEP_VERSION = os.environ.get("KEEP_VERSION", "unknown")

# Telemetry to Keep's own infrastructure (app.posthog.com) is disabled by
# default in this fork so that self-hosted instances never phone home unless
# an operator explicitly opts in with both POSTHOG_DISABLED=false and a
# POSTHOG_API_KEY they control.
POSTHOG_DISABLED = os.getenv("POSTHOG_DISABLED", "true").lower() != "false"

POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY")

posthog_client = None

if not POSTHOG_DISABLED and POSTHOG_API_KEY:
    from posthog import Posthog

    posthog_client = Posthog(
        api_key=POSTHOG_API_KEY,
        host=os.getenv("POSTHOG_HOST", "https://app.posthog.com"),
    )


def is_posthog_reachable():
    if POSTHOG_DISABLED or not POSTHOG_API_KEY:
        return False
    try:
        import requests
        from posthog import Posthog

        Posthog(
            api_key=POSTHOG_API_KEY,
            host=os.getenv("POSTHOG_HOST", "https://app.posthog.com"),
            feature_flags_request_timeout_seconds=3,
            sync_mode=True,  # Explicitly to trigger exception if it's not reachable.
        ).capture(
            get_or_creat_posthog_instance_id(),
            "connectivity_check",
        )
        return True
    except requests.exceptions.ConnectionError:
        return False
