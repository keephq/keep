import os

import posthog
from posthog import Posthog

if os.getenv("DISABLE_POSTHOG", "false") == "true":
    posthog.disabled = True


def get_random_user_id():
    if os.path.exists("RANDOM_USER_ID"):
        with open("RANDOM_USER_ID") as f:
            return f.read()
    else:
        import uuid

        random_user_id = str(uuid.uuid4())
        with open("RANDOM_USER_ID", "w") as f:
            f.write(random_user_id)
        return random_user_id


def get_posthog_client():
    posthog_api_key = (
        os.getenv("POSTHOG_API_KEY")
        or "phc_muk9qE3TfZsX3SZ9XxX52kCGJBclrjhkP9JxAQcm1PZ"
    )
    posthog_client = Posthog(api_key=posthog_api_key, host="https://app.posthog.com")
    return posthog_client
