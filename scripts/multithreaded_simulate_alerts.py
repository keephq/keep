import concurrent.futures
import logging
import os
import random
import threading
import time

import requests

from keep.providers.providers_factory import ProvidersFactory

# configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

# Thread-local storage for request sessions
thread_local = threading.local()


def get_session():
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
    return thread_local.session


def send_alert(provider_type, provider, send_alert_url, keep_api_key):
    session = get_session()
    while True:
        alert = provider.simulate_alert()
        logger.info(f"Sending alert: {alert.get('provider')}")
        try:
            env = random.choice(["production", "staging", "development"])
            response = session.post(
                send_alert_url + f"?provider_id={provider_type}-{env}",
                headers={"x-api-key": keep_api_key},
                json=alert,
            )
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            time.sleep(0.1)
            continue

        if response.status_code != 202:
            logger.error(f"Failed to send alert: {response.text}")
        else:
            logger.info("Alert sent successfully")

        time.sleep(0.2)  # Wait for 0.2 seconds before sending the next alert


def main():
    keep_api_key = os.environ.get("KEEP_API_KEY")
    keep_api_url = os.environ.get("KEEP_API_URL")
    threads = int(os.environ.get("THREADS", 32))

    if keep_api_key is None or keep_api_url is None:
        raise Exception("KEEP_API_KEY and KEEP_API_URL must be set")

    providers = ["prometheus", "grafana"]
    provider_classes = {
        provider: ProvidersFactory.get_provider_class(provider)
        for provider in providers
    }

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = []
        for _ in range(threads):
            provider_type = random.choice(providers)
            send_alert_url = f"{keep_api_url}/alerts/event/{provider_type}"
            provider = provider_classes[provider_type]
            futures.append(
                executor.submit(
                    send_alert, provider_type, provider, send_alert_url, keep_api_key
                )
            )

        # Wait for all threads to complete (which they won't, as they run indefinitely)
        concurrent.futures.wait(futures)


if __name__ == "__main__":
    main()
