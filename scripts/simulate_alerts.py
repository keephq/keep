import os
import logging
import argparse

from keep.api.core.demo_mode import simulate_alerts

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Simulate alerts for Keep API.")
    parser.add_argument(
        "--full-demo",
        action="store_true",
        help="Run the full demo including correlation rules and topology.",
    )
    args = parser.parse_args()

    default_sleep_interval = 0.2
    if args.full_demo:
        default_sleep_interval = 5

    SLEEP_INTERVAL = float(
        os.environ.get("SLEEP_INTERVAL", default_sleep_interval)
    )
    keep_api_key = os.environ.get("KEEP_API_KEY")
    keep_api_url = os.environ.get("KEEP_API_URL") or "http://localhost:8080"
    simulate_alerts(
        keep_api_key=keep_api_key,
        keep_api_url=keep_api_url,
        sleep_interval=SLEEP_INTERVAL,
        demo_correlation_rules=args.full_demo,
        demo_topology=args.full_demo,
        clean_old_incidents=args.full_demo,
    )

if __name__ == "__main__":
    main()
