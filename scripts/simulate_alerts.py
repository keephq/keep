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
    keep_api_key = os.environ.get("KEEP_API_KEY")
    keep_api_url = os.environ.get("KEEP_API_URL")
    if keep_api_key is None or keep_api_url is None:
        raise Exception("KEEP_API_KEY and KEEP_API_URL must be set")

    providers = ["prometheus", "grafana"]
    # providers = ["prometheus"]
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

        logger.info("Sending alert: {}".format(alert))
        try:
            response = requests.post(
                send_alert_url,
                headers={"x-api-key": keep_api_key},
                json=alert,
            )
        except Exception as e:
            logger.error("Failed to send alert: {}".format(e))
            time.sleep(1)
            continue

        if response.status_code != 200:
            logger.error("Failed to send alert: {}".format(response.text))
        else:
            logger.info("Alert sent successfully")

        time.sleep(0.1)  # Wait for 10 seconds before sending the next alert


if __name__ == "__main__":
    main()
