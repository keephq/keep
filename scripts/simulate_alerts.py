import logging
import os
import random
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


def main():
    GENERATE_DEDUPLICATIONS = True
    SLEEP_INTERVAL = 0.2  # Configurable sleep interval
    keep_api_key = os.environ.get("KEEP_API_KEY")
    keep_api_url = os.environ.get("KEEP_API_URL") or "http://localhost:8080"
    if keep_api_key is None or keep_api_url is None:
        raise Exception("KEEP_API_KEY and KEEP_API_URL must be set")

    providers = ["prometheus", "grafana"]
    provider_classes = {
        provider: ProvidersFactory.get_provider_class(provider)
        for provider in providers
    }
    while True:
        # choose provider
        provider_type = random.choice(providers)
        send_alert_url = "{}/alerts/event/{}".format(keep_api_url, provider_type)
        provider = provider_classes[provider_type]
        alert = provider.simulate_alert()

        # Determine number of times to send the same alert
        num_iterations = 1
        if GENERATE_DEDUPLICATIONS:
            num_iterations = random.randint(1, 3)

        for _ in range(num_iterations):
            logger.info("Sending alert: {}".format(alert))
            try:
                env = random.choice(["production", "staging", "development"])
                response = requests.post(
                    send_alert_url + f"?provider_id={provider_type}-{env}",
                    headers={"x-api-key": keep_api_key},
                    json=alert,
                )
                response.raise_for_status()  # Raise an HTTPError for bad responses
            except requests.exceptions.RequestException as e:
                logger.error("Failed to send alert: {}".format(e))
                time.sleep(SLEEP_INTERVAL)
                continue

            if response.status_code != 202:
                logger.error("Failed to send alert: {}".format(response.text))
            else:
                logger.info("Alert sent successfully")

            time.sleep(SLEEP_INTERVAL)  # Wait for the configured interval before sending the next alert


if __name__ == "__main__":
    main()
