import os

import posthog
from posthog import Posthog

if not os.getenv("DISABLE_POSTHOG"):
    posthog.disabled = True


def get_posthog_client():
    posthog_api_key = (
        os.getenv("POSTHOG_API_KEY")
        or "phc_muk9qE3TfZsX3SZ9XxX52kCGJBclrjhkP9JxAQcm1PZ"
    )
    posthog_client = Posthog(
        api_key=self.posthog_api_key, host="https://app.posthog.com"
    )
    return posthog_client
