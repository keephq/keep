#!/usr/bin/env python3
# webhook-keep

"""
This script needs to be copied to the Checkmk server to send notifications to keep.
For more details on how to configure Checkmk to send alerts to Keep, see https://docs.keephq.dev/providers/documentation/checkmk-provider.
"""

import os
import sys

import requests


# Get keep Webhook URL and API Key from environment variables
def GetPluginParams():
    env_vars = os.environ

    WebHookURL = str(env_vars.get("NOTIFY_PARAMETER_1"))
    API_KEY = str(env_vars.get("NOTIFY_PARAMETER_2"))

    # "None", if not in the environment variables
    if WebHookURL == "None" or API_KEY == "None":
        print("keep-plugin: Missing Webhook URL or API Key")
        return (
            2,
            "",
        )  # https://docs.checkmk.com/latest/en/notifications.html#_traceable_notifications

    return 0, WebHookURL


# Notification details are stored in environment variables
def GetNotificationDetails():
    # https://docs.checkmk.com/latest/en/notifications.html#environment_variables
    env_vars = os.environ
    print(env_vars)

    SITE = env_vars.get("OMD_SITE")
    WHAT = env_vars.get("NOTIFY_WHAT")
    NOTIFICATIONTYPE = env_vars.get("NOTIFY_NOTIFICATIONTYPE")

    CONTACTNAME = env_vars.get("NOTIFY_CONTACTNAME")
    CONTACTEMAIL = env_vars.get("NOTIFY_CONTACTEMAIL")
    CONTACTPAGER = env_vars.get("NOTIFY_CONTACTPAGER")

    DATE = env_vars.get("NOTIFY_DATE")
    LONGDATETIME = env_vars.get("NOTIFY_LONGDATETIME")
    SHORTDATETIME = env_vars.get("NOTIFY_SHORTDATETIME")

    HOSTNAME = env_vars.get("NOTIFY_HOSTNAME")
    HOSTALIAS = env_vars.get("NOTIFY_HOSTALIAS")
    ADDRESS = env_vars.get("NOTIFY_HOSTADDRESS")

    HOST_PROBLEM_ID = env_vars.get("NOTIFY_HOSTPROBLEMID")
    OUTPUT_HOST = env_vars.get("NOTIFY_HOSTOUTPUT")
    NOTIFY_HOSTSTATE = env_vars.get("NOTIFY_HOSTSTATE")
    LONG_OUTPUT_HOST = env_vars.get("NOTIFY_LONGHOSTOUTPUT")
    HOST_URL = env_vars.get("NOTIFY_HOSTURL")
    HOST_CHECK_COMMAND = env_vars.get("NOTIFY_HOSTCHECKCOMMAND")
    NOTIFY_LASTHOSTSHORTSTATE = env_vars.get("NOTIFY_LASTHOSTSHORTSTATE")
    EVENT_HOST = f"{NOTIFY_LASTHOSTSHORTSTATE} -> {NOTIFY_HOSTSTATE}"
    CURRENT_HOST_STATE = env_vars.get("NOTIFY_HOSTSTATE")

    SERVICE_PROBLEM_ID = env_vars.get("NOTIFY_SERVICEPROBLEMID")
    SERVICE = env_vars.get("NOTIFY_SERVICEDESC")
    OUTPUT_SERVICE = env_vars.get("NOTIFY_SERVICEOUTPUT")
    LONG_OUTPUT_SERVICE = env_vars.get("NOTIFY_LONGSERVICEOUTPUT")
    SERVICE_URL = env_vars.get("NOTIFY_SERVICEURL")
    SERVICE_CHECK_COMMAND = env_vars.get("NOTIFY_SERVICECHECKCOMMAND")
    PERF_DATA = env_vars.get("NOTIFY_SERVICEPERFDATA")
    NOTIFY_SERVICESTATE = env_vars.get("NOTIFY_SERVICESTATE")
    NOTIFY_LASTSERVICESTATE = env_vars.get("NOTIFY_LASTSERVICESTATE")
    EVENT_SERVICE = f"{NOTIFY_LASTSERVICESTATE} -> {NOTIFY_SERVICESTATE}"
    CURRENT_SERVICE_STATE = env_vars.get("NOTIFY_SERVICESTATE")

    # General information
    general = {
        "site": SITE,
        "what": WHAT,
        "notification_type": NOTIFICATIONTYPE,
        "contact_name": CONTACTNAME,
        "contact_email": CONTACTEMAIL,
        "contact_pager": CONTACTPAGER,
        "date": DATE,
        "long_date_time": LONGDATETIME,
        "short_date_time": SHORTDATETIME,
    }

    # Host related information
    host_notify = {
        "id": HOST_PROBLEM_ID,
        "summary": f"CheckMK {HOSTNAME} - {EVENT_HOST}",
        "host": HOSTNAME,
        "alias": HOSTALIAS,
        "address": ADDRESS,
        "event": EVENT_HOST,
        "output": OUTPUT_HOST,
        "long_output": LONG_OUTPUT_HOST,
        "status": CURRENT_HOST_STATE,
        "severity": "OK",
        "url": HOST_URL,
        "check_command": HOST_CHECK_COMMAND,
        **general,
    }

    # Service related information
    # See NOTIFY_NOTIFICATIONTYPE in https://docs.checkmk.com/latest/en/notifications.html#environment_variables
    if NOTIFICATIONTYPE == "RECOVERY":
        status = "UP"
    elif NOTIFICATIONTYPE == "PROBLEM":
        status = "DOWN"
    elif NOTIFICATIONTYPE == "ACKNOWLEDGEMENT":
        status = "ACKNOWLEDGED"
    # FLAPPINGSTART, FLAPPINGSTOP, FLAPPINGDISABLED, DOWNTIMESTART, DOWNTIMEEND, DOWNTIMECANCELLED, etc
    else:
        status = "DOWN"

    service_notify = {
        "id": SERVICE_PROBLEM_ID,
        "summary": f"CheckMK {HOSTNAME}/{SERVICE} {EVENT_SERVICE}",
        "host": HOSTNAME,
        "alias": HOSTALIAS,
        "address": ADDRESS,
        "service": SERVICE,
        "event": EVENT_SERVICE,
        "output": OUTPUT_SERVICE,
        "long_output": LONG_OUTPUT_SERVICE,
        "status": status,
        "severity": CURRENT_SERVICE_STATE,
        "url": SERVICE_URL,
        "check_command": SERVICE_CHECK_COMMAND,
        "perf_data": PERF_DATA,
        **general,
    }

    # Handle HOST and SERVICE notifications
    if WHAT == "SERVICE":
        notify = service_notify
    else:
        notify = host_notify

    return notify


# Start Keep workflow
def StartKeepWorkflow(WebHookURL, data):
    return_code = 0

    API_KEY = str(os.environ.get("NOTIFY_PARAMETER_2"))

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-API-KEY": API_KEY,
    }

    try:
        response = requests.post(WebHookURL, headers=headers, json=data)

        if response.status_code == 200:
            print("keep-plugin: Workflow started successfully.")
        else:
            print(
                f"keep-plugin: Failed to start the workflow. Status code: {response.status_code}"
            )
            print(response.text)
            return_code = 2
    except Exception as e:
        print(f"keep-plugin: An error occurred: {e}")
        return_code = 2

    return return_code


def main():
    print("keep-plugin: Starting...")
    return_code, WebHookURL = GetPluginParams()

    if return_code != 0:
        return return_code  # Abort, if parameter for the webhook is missing

    print("keep-plugin: Getting notification details...")
    data = GetNotificationDetails()

    print("keep-plugin: Starting Keep workflow...")
    return_code = StartKeepWorkflow(WebHookURL, data)
    print("keep-plugin: Finished.")
    return return_code


if __name__ == "__main__":
    sys.exit(main())
