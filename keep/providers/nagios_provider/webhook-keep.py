#!/usr/bin/env python3
# webhook-keep

"""
Notification script that forwards Nagios alerts to Keep.

Place this file on the Nagios server (e.g. /usr/local/nagios/libexec/webhook-keep.py),
make it executable, and reference it from a Nagios `command` definition.

The script reads two parameters from environment variables (set them via the
`-H` argument macros in the command definition, or export them in the contact
template):

    KEEP_WEBHOOK_URL  - the HTTP URL of the Keep webhook
    KEEP_API_KEY      - API key registered for the Nagios provider in Keep

All other Nagios notification context is read from the standard `NAGIOS_*`
macros that Nagios exports into the environment of notification commands.
See the Nagios docs for the full list:
https://docs.checkmk.com is not relevant; refer to
https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/macrolist.html
"""

import os
import sys

import requests

# Map of Keep payload key -> Nagios environment variable name.
# Includes both host and service macros; missing keys are dropped from the
# payload so Keep's _safe_get behaves correctly.
NAGIOS_TO_KEEP = {
    # Notification meta
    "notification_type": "NAGIOS_NOTIFICATIONTYPE",
    "notification_recipients": "NAGIOS_NOTIFICATIONRECIPIENTS",
    "notification_author": "NAGIOS_NOTIFICATIONAUTHOR",
    "notification_comment": "NAGIOS_NOTIFICATIONCOMMENT",
    # Time
    "long_date_time": "NAGIOS_LONGDATETIME",
    "short_date_time": "NAGIOS_SHORTDATETIME",
    # Host
    "host_name": "NAGIOS_HOSTNAME",
    "host_alias": "NAGIOS_HOSTALIAS",
    "host_address": "NAGIOS_HOSTADDRESS",
    "host_state": "NAGIOS_HOSTSTATE",
    "host_output": "NAGIOS_HOSTOUTPUT",
    "long_host_output": "NAGIOS_LONGHOSTOUTPUT",
    "host_check_command": "NAGIOS_HOSTCHECKCOMMAND",
    "host_problem_id": "NAGIOS_HOSTPROBLEMID",
    "host_attempt": "NAGIOS_HOSTATTEMPT",
    "host_duration": "NAGIOS_HOSTDURATION",
    "host_action_url": "NAGIOS_HOSTACTIONURL",
    "host_notes_url": "NAGIOS_HOSTNOTESURL",
    # Service
    "service_description": "NAGIOS_SERVICEDESC",
    "service_state": "NAGIOS_SERVICESTATE",
    "service_output": "NAGIOS_SERVICEOUTPUT",
    "long_service_output": "NAGIOS_LONGSERVICEOUTPUT",
    "service_check_command": "NAGIOS_SERVICECHECKCOMMAND",
    "service_problem_id": "NAGIOS_SERVICEPROBLEMID",
    "service_attempt": "NAGIOS_SERVICEATTEMPT",
    "service_duration": "NAGIOS_SERVICEDURATION",
    "service_action_url": "NAGIOS_SERVICEACTIONURL",
    "service_notes_url": "NAGIOS_SERVICENOTESURL",
    # Contact
    "contact_name": "NAGIOS_CONTACTNAME",
    "contact_email": "NAGIOS_CONTACTEMAIL",
    "contact_pager": "NAGIOS_CONTACTPAGER",
}


def build_payload() -> dict:
    payload = {}
    for keep_key, env_key in NAGIOS_TO_KEEP.items():
        value = os.environ.get(env_key)
        if value not in (None, ""):
            payload[keep_key] = value
    return payload


def main() -> int:
    webhook_url = os.environ.get("KEEP_WEBHOOK_URL")
    api_key = os.environ.get("KEEP_API_KEY")

    if not webhook_url or not api_key:
        print(
            "webhook-keep: KEEP_WEBHOOK_URL and KEEP_API_KEY must be set in the environment",
            file=sys.stderr,
        )
        return 2

    payload = build_payload()
    if not payload.get("notification_type"):
        # Nothing useful to forward; treat as no-op so Nagios doesn't loop.
        print("webhook-keep: no NAGIOS_NOTIFICATIONTYPE present, skipping", file=sys.stderr)
        return 0

    try:
        response = requests.post(
            webhook_url,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        print(f"webhook-keep: request failed: {exc}", file=sys.stderr)
        return 1

    if response.status_code >= 400:
        print(
            f"webhook-keep: keep returned {response.status_code}: {response.text[:200]}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
