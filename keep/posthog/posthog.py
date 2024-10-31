import os

import posthog
import requests

from posthog import Posthog

if os.getenv("DISABLE_POSTHOG", "false") == "true":
    posthog.disabled = True


def get_posthog_client(sync_mode=False):
    posthog_api_key = (
        os.getenv("POSTHOG_API_KEY")
        or "phc_muk9qE3TfZsX3SZ9XxX52kCGJBclrjhkP9JxAQcm1PZ"
    )
    posthog_client = Posthog(api_key=posthog_api_key, host="https://app.posthog.com", sync_mode=sync_mode)
    return posthog_client

def is_posthog_reachable():
    posthog_client = get_posthog_client(sync_mode=True)
    try:
        posthog_client.capture(
            "no_id_yet", 
            "connectivity_check",
        )
        return True
    except requests.exceptions.ConnectionError:
        return False