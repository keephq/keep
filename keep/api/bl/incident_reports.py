import json
from openai import OpenAI
from pydantic import BaseModel
from keep.api.bl.incidents_bl import IncidentBl
from typing import Optional
from keep.api.models.alert import IncidentDto, IncidentStatus
import math

incidents_json_hardcoded = """
[
    {
        "user_generated_name": "Processing Problems",
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "34498c8a-8a66-4fdd-b3f0-60dd424d8333",
        "start_time": "2025-02-03T14:42:33",
        "last_seen_time": "2025-02-03T14:42:33",
        "end_time": null,
        "creation_time": "2025-02-03T14:42:34",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": null,
        "assignee": null,
        "user_summary": "Incident 'Processing Problems' was resolved. The root cause was a deadlock error ('Deadlock found when trying to get lock; try restarting transaction') during an event processing task in the Cloud Run 'keep-api' service in the 'keephq-sandbox' project, located in 'us-central1'. Correction actions are being tracked on GitHub (issue #3159).",
        "same_incident_in_the_past_id": null,
        "id": "37692666-9b9f-44ea-9b55-86a35801002f",
        "start_time": "2025-01-27T13:49:20",
        "last_seen_time": "2025-01-27T13:49:20",
        "end_time": "2025-01-28T08:49:28",
        "creation_time": "2025-01-27T13:49:20",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Incident 'Processing Problems' was resolved. The root cause was a deadlock error ('Deadlock found when trying to get lock; try restarting transaction') during an event processing task in the Cloud Run 'keep-api' service in the 'payments-api' project, located in 'eu-central1'. Correction actions are being tracked on GitHub (issue #3159).",
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": null,
        "assignee": null,
        "user_summary": "",
        "same_incident_in_the_past_id": null,
        "id": "37692666-9b9f-44ea-9b55-86a35801113f",
        "start_time": "2025-01-27T13:49:20",
        "last_seen_time": "2025-01-27T13:49:20",
        "end_time": "2025-01-28T08:49:28",
        "creation_time": "2025-01-27T13:49:20",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Incident 'Processing Problems' was resolved. The root cause was a deadlock error ('Deadlock found when trying to get lock; try restarting transaction') during an event processing task in the Cloud Run 'keep-api' service in the 'keephq-sandbox' project, located in 'us-central1'. Correction actions are being tracked on GitHub (issue #3159).",
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "auth/users 500",
        "assignee": "",
        "user_summary": "",
        "same_incident_in_the_past_id": null,
        "id": "37fbad55-0e4d-465a-b3a4-82fe27dd7f4e",
        "start_time": "2025-02-17T13:44:43",
        "last_seen_time": "2025-02-17T13:48:05",
        "end_time": null,
        "creation_time": "2025-02-17T15:25:22",
        "alerts_count": 2,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "firing",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Processing Problems",
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "38017dd3-2b97-4c43-bd20-5e604000a220",
        "start_time": "2025-02-09T10:14:54",
        "last_seen_time": "2025-02-09T10:14:54",
        "end_time": null,
        "creation_time": "2025-02-09T10:14:55",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": null,
        "assignee": null,
        "user_summary": "Incident Title: Preset Tab 'str' object has no attribute 'hex'.Summary: Three critical alerts were triggered due to 5xx errors in the 'keep-api' service on Cloud Run Revisions. All incidents originated in the 'us-central1' location under the 'keephq-sandbox' project. Each alert specifies a different Cloud Run Revision version, but all have been resolved.",
        "same_incident_in_the_past_id": null,
        "id": "3b90d981-696d-4912-b51f-53850a13bdff",
        "start_time": "2025-01-29T10:55:13",
        "last_seen_time": "2025-01-29T12:45:31",
        "end_time": "2025-01-29T12:43:41",
        "creation_time": "2025-01-29T11:50:23",
        "alerts_count": 3,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Incident Title: Preset Tab 'str' object has no attribute 'hex'.Summary: Three critical alerts were triggered due to 5xx errors in the 'keep-api' service on Cloud Run Revisions. All incidents originated in the 'us-central1' location under the 'keephq-sandbox' project. Each alert specifies a different Cloud Run Revision version, but all have been resolved.",
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Processing Problems",
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "4199e70b-3e1f-46ee-a4b3-e68395abc91e",
        "start_time": "2025-02-02T09:03:09",
        "last_seen_time": "2025-02-02T09:03:09",
        "end_time": null,
        "creation_time": "2025-02-02T09:03:10",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": null,
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "4816a692-b44d-433c-9d1a-c0f6595b8655",
        "start_time": null,
        "last_seen_time": null,
        "end_time": null,
        "creation_time": "2025-02-03T06:44:57",
        "alerts_count": 0,
        "alert_sources": [],
        "severity": "critical",
        "status": "deleted",
        "services": [],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Both alerts are critical and report 5xx errors in the 'keep-api' Cloud Run revision located in 'us-central1'. They are temporally proximate, with Alert 2 starting just two minutes before Alert 1. The topology data indicates that 'keep-api' has a dependency on a MySQL service, but no alerts related to MySQL were reported, suggesting the issue is isolated to the 'keep-api' service itself.",
        "ai_generated_name": "Incident 1: Cloud Run Revision 5xx Errors",
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "ai",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Processing Problems",
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "4eb7552b-9226-4dbf-952a-bf9605b1ebf9",
        "start_time": "2025-01-29T16:59:19",
        "last_seen_time": "2025-01-29T16:59:19",
        "end_time": "2025-01-30T07:54:05",
        "creation_time": "2025-01-29T16:59:19",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Sorting on alerts page caused 500 errors",
        "assignee": "igor@keephq.dev",
        "user_summary": "<p>The incident involved critical errors (500 errors) on the alerts page, caused by sorting actions that led to backend failures in the alerts/query event. This was due to a mistake in the SQL query sent to MySQL. Key actions and details:•&nbsp;Sorting by status/description triggered the issue.•&nbsp;An erroneous SQL query was identified as the root cause.•&nbsp;A fix has been implemented and merged, as indicated in the Pull Request (https://github.com/keephq/keep/pull/3346).Related issues can be found in the following links:•&nbsp;Issue 3347 (https://github.com/keephq/keep/issues/3347)•&nbsp;Issue 3349 (https://github.com/keephq/keep/issues/3349)All alerts related to this incident were marked as resolved, and they were triggered by a log match condition in the GCP environment, particularly affecting the \\"keep-api\\" service.</p>",
        "same_incident_in_the_past_id": null,
        "id": "51bd75ed-cd6f-4e3e-a6e3-309583345cd1",
        "start_time": "2025-02-09T08:50:47",
        "last_seen_time": "2025-02-09T09:25:30",
        "end_time": null,
        "creation_time": "2025-02-09T10:17:34",
        "alerts_count": 4,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "The incident involved critical errors (500 errors) on the alerts page, caused by sorting actions that led to backend failures in the alerts/query event. This was due to a mistake in the SQL query sent to MySQL. Key actions and details:• Sorting by status/description triggered the issue.• An erroneous SQL query was identified as the root cause.• A fix has been implemented and merged, as indicated in the Pull Request (https://github.com/keephq/keep/pull/3346).Related issues can be found in the following links:• Issue 3347 (https://github.com/keephq/keep/issues/3347)• Issue 3349 (https://github.com/keephq/keep/issues/3349)All alerts related to this incident were marked as resolved, and they were triggered by a log match condition in the GCP environment, particularly affecting the \\"keep-api\\" service.",
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Processing Problems",
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "5371a879-ee78-43f9-bc88-b1ef7bd67366",
        "start_time": "2025-01-27T07:24:21",
        "last_seen_time": "2025-01-27T07:24:21",
        "end_time": "2025-01-27T09:41:10",
        "creation_time": "2025-01-27T07:24:22",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Extraction rule with cel source == \\"gcpmonitoring\\" fails",
        "assignee": "",
        "user_summary": "",
        "same_incident_in_the_past_id": null,
        "id": "56d8e5d4-3d3c-4df0-93d5-82ad86dea974",
        "start_time": "2025-02-17T13:59:28",
        "last_seen_time": "2025-02-17T13:59:28",
        "end_time": null,
        "creation_time": "2025-02-17T15:55:27",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "firing",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "CVS cannot use Azure ",
        "assignee": "",
        "user_summary": "Incident titled 'CVS cannot use Azure' reports a high-severity Keep API error due to an Azure AD user not being a member of authorized groups in the production environment. The issue started on 2025-02-13 and involves server IP '10-174-74-243.ec2.internal' using Alpine Linux and Node.js v20.18.3. The error remains unhandled.",
        "same_incident_in_the_past_id": null,
        "id": "5c06eefe-8b7f-4cb2-b2df-d478f3d09952",
        "start_time": "2025-02-13T21:03:02",
        "last_seen_time": "2025-02-17T15:23:50",
        "end_time": null,
        "creation_time": "2025-02-17T15:54:32",
        "alerts_count": 1,
        "alert_sources": [
            "sentry"
        ],
        "severity": "high",
        "status": "firing",
        "services": [
            "ip-10-174-74-243.ec2.internal"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Incident titled 'CVS cannot use Azure' reports a high-severity Keep API error due to an Azure AD user not being a member of authorized groups in the production environment. The issue started on 2025-02-13 and involves server IP '10-174-74-243.ec2.internal' using Alpine Linux and Node.js v20.18.3. The error remains unhandled.",
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Processing Problems (vectordev_provider.py)",
        "assignee": "",
        "user_summary": "The incident \\"Processing Problems (vectordev_provider.py)\\" involves multiple critical alerts about errors processing events within the 'keep-api' service in the Cloud Run environment in the 'keephq-sandbox' project. The issues are occurring across different revisions of the 'keep-api' service in the 'us-central1' location, indicating a persistent processing error affecting various tenants.",
        "same_incident_in_the_past_id": null,
        "id": "5dc17304-454b-47c3-a144-194d1a59bcc3",
        "start_time": "2025-02-11T11:03:08",
        "last_seen_time": "2025-02-15T09:16:55",
        "end_time": "2025-02-17T14:25:11",
        "creation_time": "2025-02-11T11:03:08",
        "alerts_count": 14,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "The incident \\"Processing Problems (vectordev_provider.py)\\" involves multiple critical alerts about errors processing events within the 'keep-api' service in the Cloud Run environment in the 'keephq-sandbox' project. The issues are occurring across different revisions of the 'keep-api' service in the 'us-central1' location, indicating a persistent processing error affecting various tenants.",
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Processing Problems",
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "65bfb189-56e3-4439-bbb2-37832c9c4349",
        "start_time": "2025-01-28T23:00:19",
        "last_seen_time": "2025-01-28T23:00:19",
        "end_time": "2025-01-29T09:20:53",
        "creation_time": "2025-01-28T23:00:20",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": null,
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "671b0bd2-3884-48e4-94d4-4ad0b2d7a8a1",
        "start_time": null,
        "last_seen_time": null,
        "end_time": null,
        "creation_time": "2025-02-02T11:56:46",
        "alerts_count": 0,
        "alert_sources": [],
        "severity": "critical",
        "status": "deleted",
        "services": [],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Alert 3 reports a 5xx error in the 'keep-api' service on Cloud Run. This alert is distinct from the event processing errors in Alerts 1 and 2, as it specifically involves HTTP 5xx status codes, indicating a different type of failure. The alert is also temporally separated from the others, occurring earlier and having been dismissed, suggesting it was resolved independently.",
        "ai_generated_name": "Cloud Run Revision 5xx Error Incident",
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "ai",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": null,
        "assignee": null,
        "user_summary": "Incident 'Manoj EKS' involves multiple alerts related to Cloud Run Revisions in the project 'keephq-sandbox'. The alerts include critical 5xx API errors and high severity provider installation failures for the 'keep-api' service in 'us-central1'. All alerts have been resolved.",
        "same_incident_in_the_past_id": null,
        "id": "6fd29c1e-c4b8-40e6-865e-f1f69c0dbd48",
        "start_time": "2025-01-29T11:44:52",
        "last_seen_time": "2025-01-29T14:59:33",
        "end_time": "2025-01-31T18:59:48",
        "creation_time": "2025-01-29T11:49:44",
        "alerts_count": 4,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Incident 'Manoj EKS' involves multiple alerts related to Cloud Run Revisions in the project 'keephq-sandbox'. The alerts include critical 5xx API errors and high severity provider installation failures for the 'keep-api' service in 'us-central1'. All alerts have been resolved.",
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "Processing Problems (prometheus_provider)",
        "assignee": "",
        "user_summary": "<p> File <span style=\\"color: rgb(163, 21, 21);\\">\\"/venv/lib/python3.11/site-packages/keep/api/tasks/process_event_task.py\\"</span>, line <span style=\\"color: rgb(9, 134, 88);\\">616</span>, <span style=\\"color: rgb(0, 0, 255);\\">in</span> process_event event <span style=\\"color: rgb(0, 0, 0);\\">=</span> provider_class.format_alert(     <span style=\\"color: rgb(0, 0, 0);\\">^^^^^^^^^^^^^^^^^^^^^^^^^^^^</span>     File <span style=\\"color: rgb(163, 21, 21);\\">\\"/venv/lib/python3.11/site-packages/keep/providers/base/base_provider.py\\"</span>, line <span style=\\"color: rgb(9, 134, 88);\\">394</span>, <span style=\\"color: rgb(175, 0, 219);\\">in</span> format_alert     <span style=\\"color: rgb(0, 16, 128);\\">formatted_alert</span> <span style=\\"color: rgb(0, 0, 0);\\">=</span> <span style=\\"color: rgb(0, 0, 255);\\">cls</span>._format_alert(event, provider_instance)     <span style=\\"color: rgb(0, 0, 0);\\">^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^</span>     File <span style=\\"color: rgb(163, 21, 21);\\">\\"/venv/lib/python3.11/site-packages/keep/providers/vectordev_provider/vectordev_provider.py\\"</span>, line <span style=\\"color: rgb(9, 134, 88);\\">58</span>, <span style=\\"color: rgb(175, 0, 219);\\">in</span> _format_alert     alert_dtos.extend(provider_class._format_alert(e[<span style=\\"color: rgb(163, 21, 21);\\">\\"message\\"</span>],provider_instance))     <span style=\\"color: rgb(0, 0, 0);\\">~^^^^^^^^^^^</span>    <span style=\\"color: rgb(38, 127, 153);\\">KeyError</span>: <span style=\\"color: rgb(163, 21, 21);\\">'message'\\"</span></p>",
        "same_incident_in_the_past_id": null,
        "id": "8cd02ee2-a891-45b7-90ab-9c1d538ec1a3",
        "start_time": "2025-02-07T03:49:12",
        "last_seen_time": "2025-02-07T05:51:24",
        "end_time": null,
        "creation_time": "2025-02-07T03:49:13",
        "alerts_count": 3,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "critical",
        "status": "firing",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "none",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "rule",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "jorge.fernandez@cores.gl mongodb installation failed",
        "assignee": "",
        "user_summary": "<p>https://console.cloud.google.com/logs/query;query=resource.type%20%3D%20%22cloud_run_revision%22%0Aresource.labels.service_name%20%3D%20%22keep-api%22%0Aresource.labels.location%20%3D%20%22us-central1%22%0A%20timestamp%20%3E%3D%20%222025-02-01T21:21:04.000Z%22%20%0A%20timestamp%20%3C%3D%20%222025-02-01T22:50:35.000Z%22%0Atrace%3D%22bd633b5d22c02120c3524c0860517afa%22;cursorTimestamp=2025-02-01T22:11:11.919356Z;startTime=2025-02-01T21:21:04Z;endTime=2025-02-01T22:50:35Z?project=keephq-sandbox&amp;inv=1&amp;invt=Abp0ww</p>",
        "same_incident_in_the_past_id": null,
        "id": "aab6a223-2f3b-4095-8ba8-b9420b1bf847",
        "start_time": "2025-02-01T22:11:05",
        "last_seen_time": "2025-02-01T22:11:05",
        "end_time": null,
        "creation_time": "2025-02-17T16:08:46",
        "alerts_count": 1,
        "alert_sources": [
            "gcpmonitoring"
        ],
        "severity": "high",
        "status": "firing",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": null,
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": "if CEL contains <apostrof>, the alerts/query breaks with 500",
        "assignee": "igor@keephq.dev",
        "user_summary": "<p>This incident is caused by an unhandled single-quote in the CEL-to-SQL conversion mechanism. It leads to a syntax error and poses a potential SQL injection risk. The process fails when managing API names containing single quotes within SQL queries.</p><p>For more details, refer to the PR https://github.com/keephq/keep/pull/3365.</p>",
        "same_incident_in_the_past_id": null,
        "id": "b2e05f71-78ed-4d87-8e19-169c868b01a5",
        "start_time": "2025-02-10T09:04:29",
        "last_seen_time": "2025-02-10T09:10:10",
        "end_time": "2025-02-10T13:20:56",
        "creation_time": "2025-02-10T09:08:09",
        "alerts_count": 5,
        "alert_sources": [
            "gcpmonitoring",
            "sentry"
        ],
        "severity": "critical",
        "status": "resolved",
        "services": [
            "null"
        ],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "This incident is caused by an unhandled single-quote in the CEL-to-SQL conversion mechanism. It leads to a syntax error and poses a potential SQL injection risk. The process fails when managing API names containing single quotes within SQL queries. For more details, refer to the [PR Link](https://github.com/keephq/keep/pull/3365).",
        "ai_generated_name": null,
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "manual",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    },
    {
        "user_generated_name": null,
        "assignee": null,
        "user_summary": null,
        "same_incident_in_the_past_id": null,
        "id": "b4e89b76-bfbe-466b-af2f-9b7ba2c9372e",
        "start_time": null,
        "last_seen_time": null,
        "end_time": null,
        "creation_time": "2025-02-03T06:44:27",
        "alerts_count": 0,
        "alert_sources": [],
        "severity": "critical",
        "status": "deleted",
        "services": [],
        "is_predicted": false,
        "is_confirmed": true,
        "generated_summary": "Both alerts are critical and report 5xx errors in the 'keep-api' Cloud Run revision located in 'us-central1'. They are temporally proximate, with Alert 2 starting just two minutes before Alert 1. The topology data indicates that 'keep-api' has a dependency on a MySQL service, but no alerts related to MySQL were reported, suggesting the issue is isolated to the 'keep-api' service itself.",
        "ai_generated_name": "Incident 1: Cloud Run Revision 5xx Errors",
        "rule_fingerprint": "",
        "fingerprint": null,
        "merged_into_incident_id": null,
        "merged_by": null,
        "merged_at": null,
        "enrichments": {},
        "incident_type": "ai",
        "incident_application": "None",
        "resolve_on": "all_resolved",
        "rule_id": null,
        "rule_name": null,
        "rule_is_deleted": null
    }
]
"""


class IncidentMetrics(BaseModel):
    total_incidents: Optional[int] = None
    resolved_incidents: Optional[int] = None
    deleted_incidents: Optional[int] = None
    unresolved_incidents: Optional[int] = None


class IncidentDurations(BaseModel):
    shortest_duration_ms: Optional[int] = None
    shortest_duration_incident_id: Optional[str] = None
    longest_duration_ms: Optional[int] = None
    longest_duration_incident_id: Optional[str] = None

class IncidentReport(BaseModel):
    incident_metrics: Optional[IncidentMetrics] = None
    top_services_affected: Optional[list[str]] = None
    common_incident_names: Optional[list[str]] = None
    severity_metrics: Optional[dict[str, str]] = None
    incident_durations: Optional[IncidentDurations] = None
    mean_time_to_detect: Optional[int] = None
    mean_time_to_resolve: Optional[int] = None
    most_occuring_incidents: Optional[list[str]] = None
    most_incident_reasons: Optional[dict[str, list[str]]] = None
    # time_based_metrics: Optional[TimeBasedMetrics] = None


# system_prompt = """
#     Generate me a report for provided incidents and response schema.

#     - Calculate Mean Time to Detect (mean_time_to_detect field) based on start_time and creation_time.
#     - Calculate Mean Time to Resolve (mean_time_to_resolve).
#     - Calculate severity metrics based on severity field. It should be dictionary with severity as key and count as value.
#     - Calculate incidents duration, such as:
#         - Shortest duration incident (shortest_duration_ms, shortest_duration_incident_id).
#         - Longest duration incident (longest_duration_ms, longest_duration_incident_id).
#     - Calculate top services affected (top_services_affected).
#     - Calculate the most occuring incidents and distict them by meaning based on name and summary. If incident name means the same, do not include it.
#     - Calculate the most incident reasons based on name and description.
# """

system_prompt = """
Generate an incident report based on the provided incidents dataset and response schema. Ensure all calculated metrics follow the specified format for consistency.

**Calculations and Metrics:**

1. **Mean Time to Detect (MTTD)**
   - Skip mean_time_to_detect

2. **Mean Time to Resolve (MTTR)**
   - Skip mean_time_to_resolve

3. **Severity Metrics**
   - Create a dictionary `severity_metrics` where:
     - Keys represent unique severity levels.
     - Values represent the count of incidents with that severity.

4. **Incident Duration Metrics**
   - Skip incident_durations

5. **Top Services Affected**
   - Compute `top_services_affected` as a ranked list of the most frequently affected services.
   - Output as a dictionary with service names as keys and the number of incidents as values.

6. **Most Frequent Incidents (Grouped by Meaning)**
   - Group incidents by their `name` and `summary`.
   - If multiple incidents have different names but the same meaning, only include one.
   - Output `most_frequent_incidents` as a list of distinct incident names with their occurrence count.

7. **Most Frequent Incident Reasons**
   - Identify the most common root causes by analyzing `name` and `description`.
   - Group similar reasons to avoid duplicates.
   - Output `most_frequent_reasons` as a dictionary with reasons as keys and list of incident ids as values.
"""


class IncidentReports:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.incidents_bl = IncidentBl(
            tenant_id=tenant_id, session=None, pusher_client=None, user=None
        )
        self.open_ai_client = OpenAI()

    def get_incident_reports(
        self, incidents_query_cel: str, allowed_incident_ids: list[str]
    ) -> IncidentReport:
        incidents = self.__get_incidents(incidents_query_cel, allowed_incident_ids)
        incidents_json = json.dumps([item.dict() for item in incidents], default=str)

        response = self.open_ai_client.chat.completions.create(
            model="gpt-4o-2024-08-06",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": incidents_json},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "IncidentReport",
                    "schema": IncidentReport.schema(),
                },
            },
            # tools=tools,
            # tool_choice="auto",
            seed=1239,
            temperature=0.2,
        )

        foster = response.choices[0].message.content
        report = IncidentReport(**json.loads(foster))
        resolved_incidents = [
            incident
            for incident in incidents
            if incident.status == IncidentStatus.RESOLVED
        ]
        report.mean_time_to_detect = self.__calculate_mttd(resolved_incidents)
        report.mean_time_to_resolve = self.__calculate_mttr(resolved_incidents)
        report.incident_durations = self.__calculate_durations(resolved_incidents)

        return report

    def __calculate_mttd(self, resolved_incidents: list[IncidentDto]) -> int:
        duration_sum = 0

        for incident in resolved_incidents:
            duration_sum += (
                incident.creation_time - incident.start_time
            ).total_seconds()

        return math.ceil(duration_sum / len(resolved_incidents))

    def __calculate_mttr(self, resolved_incidents: list[IncidentDto]) -> int:
        duration_sum = 0
        filtered_incidents = [
            incident for incident in resolved_incidents if incident.end_time
        ]
        for incident in filtered_incidents:
            start_time = incident.start_time or incident.creation_time
            duration_sum += (incident.end_time - start_time).total_seconds()

        return math.ceil(duration_sum / len(filtered_incidents))

    def __calculate_durations(
        self, resolved_incidents: list[IncidentDto]
    ) -> IncidentDurations:
        shortest_duration_ms = None
        shortest_duration_incident_id = None
        longest_duration_ms = None
        longest_duration_incident_id = None

        for incident in resolved_incidents:
            start_time = incident.start_time or incident.creation_time
            if not start_time or not incident.end_time:
                continue

            duration = (incident.end_time - start_time).total_seconds()
            if not shortest_duration_ms or duration < shortest_duration_ms:
                shortest_duration_ms = duration
                shortest_duration_incident_id = incident.id

            if not longest_duration_ms or duration > longest_duration_ms:
                longest_duration_ms = duration
                longest_duration_incident_id = incident.id

        return IncidentDurations(
            shortest_duration_ms=shortest_duration_ms,
            shortest_duration_incident_id=str(shortest_duration_incident_id),
            longest_duration_ms=longest_duration_ms,
            longest_duration_incident_id=str(longest_duration_incident_id),
        )

    def __get_incidents(
        self, incidents_query_cel: str, allowed_incident_ids: list[str]
    ) -> list[IncidentDto]:
        hardcoded_incidents_dicts = json.loads(incidents_json_hardcoded)
        print("f")
        return [
            IncidentDto(**incident_dict) for incident_dict in hardcoded_incidents_dicts
        ]

        query_result = self.incidents_bl.query_incidents(
            tenant_id=self.tenant_id,
            cel=incidents_query_cel,
            limit=100,
            offset=0,
            allowed_incident_ids=allowed_incident_ids,
            is_confirmed=True,
        )
        return query_result.items
