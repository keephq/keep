import os
import logging
import argparse

import asyncio

from keep.api.core.demo_mode import simulate_alerts, simulate_alerts_worker, simulate_alerts_async

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(description="Simulate alerts for Keep API.")
    parser.add_argument(
        "--num",
        action="store",
        dest="num",
        type=int,
        help="Number of alerts to simulate."
    )
    parser.add_argument(
        "--full-demo",
        action="store_true",
        help="Run the full demo including correlation rules and topology.",
    )
    parser.add_argument("--rps", type=int, help="Base requests per second")
    parser.add_argument("--workers", "-w", type=int, default=1, help="Amount of background workers to send alerts")

    args = parser.parse_args()
    rps = args.rps

    default_sleep_interval = 0.2
    if args.full_demo:
        default_sleep_interval = 5
        rps = 0

    SLEEP_INTERVAL = float(
        os.environ.get("SLEEP_INTERVAL", default_sleep_interval)
    )
    keep_api_key = os.environ.get("KEEP_API_KEY")
    keep_api_url = os.environ.get("KEEP_API_URL") or "http://localhost:8080"

    for i in range(args.workers):
        asyncio.create_task(simulate_alerts_worker(i, keep_api_key, rps))

    await simulate_alerts_async(
        keep_api_key=keep_api_key,
        keep_api_url=keep_api_url,
        sleep_interval=SLEEP_INTERVAL,
        demo_correlation_rules=args.full_demo,
        demo_topology=args.full_demo,
        clean_old_incidents=args.full_demo,
        demo_ai=args.full_demo,
        count=args.num,
        target_rps=rps,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        print("Closing Loop")
