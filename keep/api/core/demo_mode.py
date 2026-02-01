import asyncio
import logging
import logging.config
import os
import random
import time
from dataclasses import dataclass
from uuid import uuid4
from typing import Any, Optional

import aiohttp

from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.api.logging import CONFIG
from keep.providers.providers_factory import ProvidersFactory

logging.config.dictConfig(CONFIG)
logger = logging.getLogger(__name__)

KEEP_LIVE_DEMO_MODE = os.environ.get("KEEP_LIVE_DEMO_MODE", "false").lower() == "true"
GENERATE_DEDUPLICATIONS = os.environ.get("GENERATE_DEDUPLICATIONS", "false").lower() == "true"


@dataclass(frozen=True)
class DemoConfig:
    api_url: str
    api_key: str
    # traffic shaping
    target_rps: float = 5.0
    concurrency: int = 10
    queue_max: int = 10_000
    # demo features
    demo_ai: bool = False
    demo_topology: bool = False
    demo_correlation_rules: bool = False
    # behavior
    environments: tuple[str, ...] = ("production", "staging", "development")


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


def _parse_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _choose_provider(providers_config: list[dict[str, Any]]) -> str:
    providers = [p["type"] for p in providers_config]
    weights = [p["weight"] for p in providers_config]
    return random.choices(providers, weights=weights, k=1)[0]


def _normalize_alert(alert: dict[str, Any], provider_type: str, env: str) -> dict[str, Any]:
    # Make sure environment is present in a predictable way
    alert = dict(alert)
    alert.setdefault("fingerprint", str(uuid4()))
    alert.setdefault("source", [provider_type])
    alert.setdefault("environment", env)
    return alert


async def _get_installed_providers(http: aiohttp.ClientSession, cfg: DemoConfig) -> dict[str, str]:
    url = f"{cfg.api_url}/providers"
    async with http.get(url, headers={"x-api-key": cfg.api_key}) as resp:
        text = await resp.text()
        if resp.status >= 400:
            raise RuntimeError(f"Failed to fetch providers: {resp.status} {text}")
        data = await resp.json()

    installed = data.get("installed_providers", []) or []
    mapping: dict[str, str] = {}
    for p in installed:
        p_type = p.get("type")
        p_id = p.get("id")
        if p_type and p_id:
            mapping[p_type] = p_id
    return mapping


async def producer(queue: asyncio.Queue, cfg: DemoConfig, stop: asyncio.Event) -> None:
    providers_config = [
        {"type": "prometheus", "weight": 3},
        {"type": "grafana", "weight": 1},
        {"type": "cloudwatch", "weight": 1},
        {"type": "datadog", "weight": 1},
        {"type": "sentry", "weight": 2},
        {"type": "gcpmonitoring", "weight": 1},
    ]

    provider_classes = {
        p["type"]: ProvidersFactory.get_provider_class(p["type"]) for p in providers_config
    }

    # Simple token bucket scheduling
    interval = 1.0 / cfg.target_rps if cfg.target_rps > 0 else 0.0
    next_ts = time.perf_counter()

    while not stop.is_set():
        provider_type = _choose_provider(providers_config)
        env = random.choice(cfg.environments)

        provider_cls = provider_classes[provider_type]
        alert = provider_cls.simulate_alert()
        alert = _normalize_alert(alert, provider_type, env)

        # Dedup generation
        iterations = random.randint(1, 3) if GENERATE_DEDUPLICATIONS else 1

        for _ in range(iterations):
            # Backpressure: wait if queue is full
            await queue.put((provider_type, alert))

        if interval > 0:
            next_ts += interval
            sleep_for = next_ts - time.perf_counter()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
            else:
                # If we're lagging, don't sleep. Just keep going.
                next_ts = time.perf_counter()


async def worker(worker_id: int, queue: asyncio.Queue, cfg: DemoConfig, stop: asyncio.Event) -> None:
    headers = {
        "X-API-KEY": cfg.api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    timeout = aiohttp.ClientTimeout(total=15)

    sent = 0
    start_ts = time.perf_counter()

    async with aiohttp.ClientSession(timeout=timeout) as http:
        # cache installed providers once per worker session (optional)
        try:
            installed_provider_ids = await _get_installed_providers(http, cfg)
        except Exception:
            installed_provider_ids = {}

        while not stop.is_set():
            try:
                provider_type, alert = await queue.get()
            except asyncio.CancelledError:
                break

            params = {}
            pid = installed_provider_ids.get(provider_type)
            if pid:
                params["provider_id"] = pid
            else:
                # Fallback provider id convention used in your original code
                params["provider_id"] = f"{provider_type}-{alert.get('environment', 'production')}"

            url = f"{cfg.api_url}/alerts/event/{provider_type}"

            try:
                async with http.post(url, params=params, json=alert, headers=headers) as resp:
                    body = await resp.text()
                    if resp.status >= 400:
                        logger.warning(
                            "worker=%d failed status=%d body=%s",
                            worker_id,
                            resp.status,
                            body[:500],
                        )
                    else:
                        sent += 1
            except Exception as e:
                logger.exception("worker=%d request error: %s", worker_id, str(e))
            finally:
                queue.task_done()

            # periodic stats, not a log firehose
            if sent and sent % 200 == 0:
                elapsed = time.perf_counter() - start_ts
                rps = sent / elapsed if elapsed > 0 else 0.0
                logger.info("worker=%d sent=%d rps=%.2f q=%d", worker_id, sent, rps, queue.qsize())


async def run_demo(cfg: DemoConfig) -> None:
    if not cfg.api_key:
        raise RuntimeError("No API key provided. Set KEEP_READ_ONLY_BYPASS_KEY or pass cfg.api_key.")

    stop = asyncio.Event()
    queue: asyncio.Queue = asyncio.Queue(maxsize=cfg.queue_max)

    tasks: list[asyncio.Task] = []

    try:
        tasks.append(asyncio.create_task(producer(queue, cfg, stop), name="producer"))

        for i in range(cfg.concurrency):
            tasks.append(asyncio.create_task(worker(i, queue, cfg, stop), name=f"worker-{i}"))

        # Run until killed
        await asyncio.gather(*tasks)

    except asyncio.CancelledError:
        pass
    finally:
        stop.set()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    api_url = os.environ.get("KEEP_API_URL") or "http://localhost:8080"
    api_key = os.environ.get("KEEP_READ_ONLY_BYPASS_KEY") or os.environ.get("KEEP_API_KEY") or ""

    cfg = DemoConfig(
        api_url=api_url,
        api_key=api_key,
        target_rps=float(os.environ.get("DEMO_TARGET_RPS", "5")),
        concurrency=int(os.environ.get("DEMO_CONCURRENCY", "10")),
        demo_ai=_parse_bool("DEMO_AI", False),
        demo_topology=_parse_bool("DEMO_TOPOLOGY", False),
        demo_correlation_rules=_parse_bool("DEMO_CORRELATION_RULES", False),
    )

    # If you insist on demo mode existing, at least make it controlled.
    if KEEP_LIVE_DEMO_MODE:
        asyncio.run(run_demo(cfg))
    else:
        logger.info("KEEP_LIVE_DEMO_MODE is false. Not running demo traffic.")