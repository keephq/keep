import os
import logging
import asyncio

from keep.api.core.demo_mode_runner import simulate_alerts

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


async def main():
    SLEEP_INTERVAL = float(os.environ.get("SLEEP_INTERVAL", 0.2))  # Configurable sleep interval from env variable
    keep_api_key = os.environ.get("KEEP_API_KEY")
    keep_api_url = os.environ.get("KEEP_API_URL") or "http://localhost:8080"
    await simulate_alerts(
        keep_api_key=keep_api_key,
        keep_api_url=keep_api_url,
        sleep_interval=SLEEP_INTERVAL,
        demo_correlation_rules=False,
    )


if __name__ == "__main__":
    asyncio.run(main())
