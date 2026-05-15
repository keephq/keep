#!/usr/bin/env python3
"""Fire SNMP traps at a running Keep SNMP provider and verify alert ingestion."""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import socket
import subprocess
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

warnings.filterwarnings(
    "ignore",
    message="The 'pysnmp-lextudio' package is deprecated.*",
    category=RuntimeWarning,
)

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    Integer,
    NotificationType,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    sendNotification,
)

AUTH_FAILURE_TRAP_OID = "1.3.6.1.6.3.1.1.5.5"
COLD_START_TRAP_OID = "1.3.6.1.6.3.1.1.5.1"
LINK_DOWN_TRAP_OID = "1.3.6.1.6.3.1.1.5.3"
LINK_UP_TRAP_OID = "1.3.6.1.6.3.1.1.5.4"
IF_INDEX_OID = "1.3.6.1.2.1.2.2.1.1.5"
RECENT_SKEW_SECONDS = 5


@dataclass(frozen=True)
class TrapSpec:
    display_name: str
    expected_alert_name: str
    trap_oid: str
    expected_severity: str
    expected_status: str
    varbinds: tuple[tuple[str, Any], ...]


TRAPS = (
    TrapSpec(
        display_name="linkDown",
        expected_alert_name="linkDown",
        trap_oid=LINK_DOWN_TRAP_OID,
        expected_severity="critical",
        expected_status="firing",
        varbinds=((IF_INDEX_OID, Integer(5)),),
    ),
    TrapSpec(
        display_name="linkUp",
        expected_alert_name="linkUp",
        trap_oid=LINK_UP_TRAP_OID,
        expected_severity="info",
        expected_status="resolved",
        varbinds=((IF_INDEX_OID, Integer(5)),),
    ),
    TrapSpec(
        display_name="coldStart",
        expected_alert_name="coldStart",
        trap_oid=COLD_START_TRAP_OID,
        expected_severity="info",
        expected_status="firing",
        varbinds=(),
    ),
    TrapSpec(
        display_name="authFailure",
        expected_alert_name="authenticationFailure",
        trap_oid=AUTH_FAILURE_TRAP_OID,
        expected_severity="warning",
        expected_status="firing",
        varbinds=(),
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Send live SNMP traps to a Keep SNMP provider and verify Keep's "
            "alerts API and consumer status."
        )
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("KEEP_BASE_URL", "http://localhost:8080"),
        help="Keep API base URL.",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("KEEP_API_KEY")
        or _read_env_value(("KEEP_API_KEY", "SECRET_KEY")),
        help="Keep API key. If omitted, requests are sent without X-API-KEY.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="SNMP listener host.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1162,
        help="SNMP listener UDP port.",
    )
    parser.add_argument(
        "--community",
        default="public",
        help="SNMP v2c community string.",
    )
    parser.add_argument(
        "--provider-status-id",
        default="snmp-test",
        help=(
            "Provider identifier to look for under /status after the junk-packet "
            "check. Use the runtime listener id if it differs from the install payload."
        ),
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=30.0,
        help="Maximum seconds to wait for alerts to appear in Keep.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval while waiting for alerts.",
    )
    parser.add_argument(
        "--inter-trap-delay",
        type=float,
        default=0.5,
        help="Delay between emitted traps.",
    )
    parser.add_argument(
        "--pr-output",
        default=None,
        help="Optional path to write the PR description evidence snippet.",
    )
    return parser.parse_args()


def _read_env_value(keys: tuple[str, ...]) -> str | None:
    env_path = Path(".env")
    if not env_path.exists():
        return None

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    for key in keys:
        if values.get(key):
            return values[key]
    return None


def _parse_timestamp(value: str) -> dt.datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _is_recent(alert: dict[str, Any], started_at: dt.datetime) -> bool:
    last_received = alert.get("lastReceived")
    if not last_received:
        return False
    cutoff = started_at - dt.timedelta(seconds=RECENT_SKEW_SECONDS)
    return _parse_timestamp(last_received) >= cutoff


def _redacted_display_command(url: str, api_key: str | None) -> str:
    cmd = ["curl", "-fsS", url]
    if api_key:
        cmd.extend(["-H", "X-API-KEY: <redacted>"])
    return " ".join(json.dumps(part) if " " in part else part for part in cmd)


def _curl_json(
    base_url: str,
    path: str,
    api_key: str | None,
) -> tuple[Any, str]:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    cmd = ["curl", "-fsS", url]
    if api_key:
        cmd.extend(["-H", f"X-API-KEY: {api_key}"])
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"curl failed for {path}: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response from {path}: {proc.stdout}") from exc
    return payload, _redacted_display_command(url, api_key)


def _select_recent_current_alerts(
    alerts: list[dict[str, Any]],
    started_at: dt.datetime,
) -> dict[str, dict[str, Any]]:
    matches: dict[str, dict[str, Any]] = {}
    for trap in TRAPS:
        for alert in alerts:
            labels = alert.get("labels") or {}
            if labels.get("trap_oid") != trap.trap_oid:
                continue
            if not _is_recent(alert, started_at):
                continue
            matches[trap.trap_oid] = alert
            break
    return matches


def _build_alert_summary(alert: dict[str, Any]) -> dict[str, Any]:
    labels = alert.get("labels") or {}
    return {
        "name": alert.get("name"),
        "severity": alert.get("severity"),
        "status": alert.get("status"),
        "fingerprint": alert.get("fingerprint"),
        "trap_oid": labels.get("trap_oid"),
        "source_address": labels.get("source_address"),
        "lastReceived": alert.get("lastReceived"),
    }


def _find_link_history_entries(
    history: list[dict[str, Any]],
    started_at: dt.datetime,
) -> list[dict[str, Any]]:
    recent_entries = []
    for alert in history:
        labels = alert.get("labels") or {}
        trap_oid = labels.get("trap_oid")
        if trap_oid not in {LINK_DOWN_TRAP_OID, LINK_UP_TRAP_OID}:
            continue
        if not _is_recent(alert, started_at):
            continue
        recent_entries.append(alert)
    return recent_entries


async def _send_trap(host: str, port: int, community: str, trap: TrapSpec) -> None:
    engine = SnmpEngine()
    try:
        error_indication, error_status, error_index, _ = await sendNotification(
            engine,
            CommunityData(community, mpModel=1),
            await UdpTransportTarget.create((host, port)),
            ContextData(),
            "trap",
            NotificationType(ObjectIdentity(trap.trap_oid)).addVarBinds(
                *[
                    ObjectType(ObjectIdentity(oid), value)
                    for oid, value in trap.varbinds
                ]
            ),
        )
    finally:
        engine.closeDispatcher()

    if error_indication:
        raise RuntimeError(f"{trap.display_name}: {error_indication}")
    if error_status:
        raise RuntimeError(
            f"{trap.display_name}: {error_status.prettyPrint()} at index {error_index}"
        )
    print(f"SENT  {trap.display_name} ({trap.trap_oid})")


async def _send_all_traps(args: argparse.Namespace) -> dt.datetime:
    started_at = dt.datetime.now(tz=dt.timezone.utc)
    print(f"Firing test traps at {args.host}:{args.port} ...")
    for index, trap in enumerate(TRAPS):
        await _send_trap(args.host, args.port, args.community, trap)
        if index != len(TRAPS) - 1:
            await asyncio.sleep(args.inter_trap_delay)
    return started_at


def _verify_alert_state(
    base_url: str,
    api_key: str | None,
    started_at: dt.datetime,
    poll_timeout: float,
    poll_interval: float,
) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    deadline = time.time() + poll_timeout
    last_reason = "alerts not yet available"

    while time.time() < deadline:
        alerts_payload, alerts_cmd = _curl_json(base_url, "/alerts?limit=1000", api_key)
        if not isinstance(alerts_payload, list):
            raise RuntimeError(f"Unexpected /alerts payload: {alerts_payload}")

        current_alerts = _select_recent_current_alerts(alerts_payload, started_at)

        cold_start = current_alerts.get(COLD_START_TRAP_OID)
        auth_failure = current_alerts.get(AUTH_FAILURE_TRAP_OID)
        link_up = current_alerts.get(LINK_UP_TRAP_OID)

        if (
            not cold_start
            or cold_start.get("name") != "coldStart"
            or cold_start.get("severity") != "info"
            or cold_start.get("status") != "firing"
        ):
            last_reason = "coldStart alert missing or wrong state"
            time.sleep(poll_interval)
            continue

        if (
            not auth_failure
            or auth_failure.get("name") != "authenticationFailure"
            or auth_failure.get("severity") != "warning"
            or auth_failure.get("status") != "firing"
        ):
            last_reason = "authenticationFailure alert missing or wrong state"
            time.sleep(poll_interval)
            continue

        if (
            not link_up
            or link_up.get("name") != "linkUp"
            or link_up.get("severity") != "info"
            or link_up.get("status") != "resolved"
        ):
            last_reason = "linkUp alert missing or not resolved"
            time.sleep(poll_interval)
            continue

        shared_fingerprint = link_up.get("fingerprint")
        if not shared_fingerprint:
            last_reason = "linkUp alert has no fingerprint"
            time.sleep(poll_interval)
            continue

        history_payload, history_cmd = _curl_json(
            base_url,
            f"/alerts/{shared_fingerprint}/history",
            api_key,
        )
        if not isinstance(history_payload, list):
            raise RuntimeError(
                "Unexpected /alerts/<fingerprint>/history payload: "
                f"{history_payload}"
            )

        link_history = _find_link_history_entries(history_payload, started_at)
        history_by_oid = {
            (entry.get("labels") or {}).get("trap_oid"): entry for entry in link_history
        }
        link_down = history_by_oid.get(LINK_DOWN_TRAP_OID)
        if not link_down:
            last_reason = "linkDown history entry missing"
            time.sleep(poll_interval)
            continue

        if (
            link_down.get("name") != "linkDown"
            or link_down.get("severity") != "critical"
            or link_down.get("status") != "firing"
        ):
            last_reason = "linkDown history entry has wrong severity/status"
            time.sleep(poll_interval)
            continue

        if link_down.get("fingerprint") != shared_fingerprint:
            last_reason = "linkDown and linkUp fingerprints differ"
            time.sleep(poll_interval)
            continue

        return (
            {
                "current_alerts": [
                    _build_alert_summary(link_up),
                    _build_alert_summary(cold_start),
                    _build_alert_summary(auth_failure),
                ],
                "shared_fingerprint": shared_fingerprint,
            },
            {
                "link_history": [
                    _build_alert_summary(link_down),
                    _build_alert_summary(link_up),
                ],
            },
            alerts_cmd,
            history_cmd,
        )

    raise RuntimeError(f"Timed out waiting for verified alert state: {last_reason}")


def _send_junk_packet(host: str, port: int) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.sendto(b"garbage", (host, port))
    finally:
        sock.close()
    print(f"SENT  junk UDP payload to {host}:{port}")


def _verify_consumer_status(
    base_url: str,
    api_key: str | None,
    provider_status_id: str | None,
) -> tuple[dict[str, Any], str]:
    status_payload, status_cmd = _curl_json(base_url, "/status", api_key)
    consumers = (status_payload.get("consumer") or {}).get("consumers") or []
    if not isinstance(consumers, list):
        raise RuntimeError(f"Unexpected /status payload: {status_payload}")

    if provider_status_id:
        for consumer in consumers:
            if consumer.get("provider_id") == provider_status_id:
                if (consumer.get("status") or {}).get("status") != "running":
                    raise RuntimeError(
                        f"Provider {provider_status_id} is not running after junk packet: {consumer}"
                    )
                return consumer, status_cmd

    running_consumers = [
        consumer
        for consumer in consumers
        if (consumer.get("status") or {}).get("status") == "running"
    ]
    if len(running_consumers) == 1:
        return running_consumers[0], status_cmd

    raise RuntimeError(
        "Could not uniquely identify the SNMP consumer under /status. "
        "Pass --provider-status-id explicitly."
    )


def _build_pr_snippet(
    alerts_cmd: str,
    alerts_summary: dict[str, Any],
    history_cmd: str,
    history_summary: dict[str, Any],
    status_cmd: str,
    consumer_summary: dict[str, Any],
) -> str:
    sections = [
        "### SNMP smoke test",
        "",
        f"Current alert view (`{alerts_cmd}`):",
        "```json",
        json.dumps(alerts_summary, indent=2),
        "```",
        "",
        f"Shared-fingerprint history (`{history_cmd}`):",
        "```json",
        json.dumps(history_summary, indent=2),
        "```",
        "",
        f"Consumer status after junk packet (`{status_cmd}`):",
        "```json",
        json.dumps(consumer_summary, indent=2),
        "```",
    ]
    return "\n".join(sections)


async def _async_main(args: argparse.Namespace) -> int:
    started_at = await _send_all_traps(args)
    alerts_summary, history_summary, alerts_cmd, history_cmd = _verify_alert_state(
        base_url=args.base_url,
        api_key=args.api_key,
        started_at=started_at,
        poll_timeout=args.poll_timeout,
        poll_interval=args.poll_interval,
    )

    _send_junk_packet(args.host, args.port)
    time.sleep(1.0)

    consumer_summary, status_cmd = _verify_consumer_status(
        base_url=args.base_url,
        api_key=args.api_key,
        provider_status_id=args.provider_status_id,
    )

    pr_snippet = _build_pr_snippet(
        alerts_cmd=alerts_cmd,
        alerts_summary=alerts_summary,
        history_cmd=history_cmd,
        history_summary=history_summary,
        status_cmd=status_cmd,
        consumer_summary=consumer_summary,
    )

    print("")
    print("Verification passed.")
    print(pr_snippet)

    if args.pr_output:
        Path(args.pr_output).write_text(pr_snippet + "\n", encoding="utf-8")
        print(f"\nWrote PR description snippet to {args.pr_output}")

    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
