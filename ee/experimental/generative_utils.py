import logging
import os

import numpy as np
from openai import OpenAI

from keep.api.core.db import get_incident_by_id

from keep.api.models.db.alert import Incident

logger = logging.getLogger(__name__)

SUMMARY_GENERATOR_VERBOSE_NAME = "Summary generator v0.1"
NAME_GENERATOR_VERBOSE_NAME = "Name generator v0.1"
MAX_SUMMARY_LENGTH = 900
MAX_NAME_LENGTH = 75

def generate_incident_summary(
    incident: Incident,
    use_n_alerts_for_summary: int = -1,
    generate_summary: str = None,
    max_summary_length: int = None,
) -> str:
    if "OPENAI_API_KEY" not in os.environ:
        logger.error(
            "OpenAI API key is not set. Incident summary generation is not available.",
            extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME,
                   "incident_id": incident.id, "tenant_id": incident.tenant_id}
        )
        return ""

    if "OPENAI_API_URL" not in os.environ:
        logger.error(
            "OpenAI API url is not set. You use OpenAi models.",
            extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME,
                   "incident_id": incident.id, "tenant_id": incident.tenant_id}
        )
        return ""

    if not generate_summary:
        generate_summary = os.environ.get("GENERATE_INCIDENT_SUMMARY", "True")

    if generate_summary == "False":
        logger.info(f"Incident summary generation is disabled. Aborting.",
                    extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})
        return ""

    if incident.user_summary:
        return ""

    if not max_summary_length:
        max_summary_length = os.environ.get(
            "MAX_SUMMARY_LENGTH", MAX_SUMMARY_LENGTH)

    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        incident = get_incident_by_id(incident.tenant_id, incident.id)

        description_strings = np.unique(
            [f'{alert.event["name"]}' for alert in incident.alerts]
        ).tolist()

        if use_n_alerts_for_summary > 0:
            incident_description = "\n".join(
                description_strings[:use_n_alerts_for_summary]
            )
        else:
            incident_description = "\n".join(description_strings)

        timestamps = [alert.timestamp for alert in incident.alerts]
        incident_start = min(timestamps).replace(microsecond=0)
        incident_end = max(timestamps).replace(microsecond=0)

        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        summary = (
            client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a very skilled DevOps specialist who can summarize any incident based on alert descriptions.
                When provided with information, summarize it in a 2-3 sentences explaining what happened and when.
                ONLY SUMMARIZE WHAT YOU SEE. In the end add information about potential scenario of the incident.
                When provided with information, answer with max a {int(max_summary_length * 0.9)} symbols excerpt
                describing incident thoroughly.

                EXAMPLE:
                An incident occurred between 2022-11-17 14:11:04 and 2022-11-22 22:19:04, involving a
                total of 200 alerts. The alerts indicated critical and warning issues such as high CPU and memory
                usage in pods and nodes, as well as stuck Kubernetes Daemonset rollout. Potential incident scenario:
                Kubernetes Daemonset rollout stuck due to high CPU and memory usage in pods and nodes. This caused a
                long tail of alerts on various topics.""",
                    },
                    {
                        "role": "user",
                        "content": f"""Here are  alerts of an incident for summarization:\n{incident_description}\n This incident started  on
                {incident_start}, ended on {incident_end}, included {incident.alerts_count} alerts.""",
                    },
                ],
            )
            .choices[0]
            .message.content
        )

        logger.info(f"Generated incident summary with length {len(summary)} symbols",
                    extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})

        if len(summary) > max_summary_length:
            logger.info(f"Generated incident summary is too long. Applying smart truncation",
                        extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})

            summary = (
                client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": f"""You are a very skilled DevOps specialist who can summarize any incident based on a description.
                    When provided with information, answer with max a {int(max_summary_length * 0.9)} symbols excerpt describing
                    incident thoroughly.
                    """,
                        },
                        {
                            "role": "user",
                            "content": f"""Here is the description of an incident for summarization:\n{summary}""",
                        },
                    ],
                )
                .choices[0]
                .message.content
            )

            logger.info(f"Generated new incident summary with length {len(summary)} symbols",
                        extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})

            if len(summary) > max_summary_length:
                logger.info(f"Generated incident summary is too long. Applying hard truncation",
                            extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})
                summary = summary[: max_summary_length]

        return summary
    except Exception as e:
        logger.error(f"Error in generating incident summary: {e}",
                     extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})
        return ""


def generate_incident_name(incident: Incident, generate_name: str = None, max_name_length: int = None, use_n_alerts_for_name: int = -1) -> str:
    if "OPENAI_API_KEY" not in os.environ:
        logger.error(
            "OpenAI API key is not set. Incident name generation is not available.",
            extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME,
                   "incident_id": incident.id, "tenant_id": incident.tenant_id}
        )
        return ""

    if "OPENAI_API_URL" not in os.environ:
        logger.error(
            "OpenAI API url is not set. You use OpenAi models.",
            extra={"algorithm": SUMMARY_GENERATOR_VERBOSE_NAME,
                   "incident_id": incident.id, "tenant_id": incident.tenant_id}
        )
        return ""

    if not generate_name:
        generate_name = os.environ.get("GENERATE_INCIDENT_NAME", "True")

    if generate_name == "False":
        logger.info(f"Incident name generation is disabled. Aborting.",
                    extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})
        return ""

    if incident.user_generated_name:
        return ""

    if not max_name_length:
        max_name_length = os.environ.get(
            "MAX_NAME_LENGTH", MAX_NAME_LENGTH)

    try:
        client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ["OPENAI_API_URL"]
        )

        incident = get_incident_by_id(incident.tenant_id, incident.id)

        description_strings = np.unique(
            [f'{alert.event["name"]}' for alert in incident.alerts]).tolist()

        if use_n_alerts_for_name > 0:
            incident_description = "\n".join(
                description_strings[:use_n_alerts_for_name])
        else:
            incident_description = "\n".join(description_strings)

        timestamps = [alert.timestamp for alert in incident.alerts]
        incident_start = min(timestamps).replace(microsecond=0)

        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        name = client.chat.completions.create(model=model, messages=[
            {
                "role": "system",
                "content": f"""You are a very skilled DevOps specialist who can name any incident based on alert descriptions. 
                When provided with information, output a short descriptive name of incident that could cause these alerts. 
                Add information about start time to the name. ONLY USE WHAT YOU SEE. Answer with max a {int(max_name_length * 0.9)}
                symbols excerpt.
                
                EXAMPLE:
                Kubernetes rollout stuck (started on 2022.11.17 14:11)"""
            },
            {
                "role": "user",
                "content": f"""This incident started  on {incident_start}. 
                Here are  alerts of an incident:\n{incident_description}\n"""
            }
        ]).choices[0].message.content

        logger.info(f"Generated incident name with length {len(name)} symbols",
                    extra={"incident_id": incident.id, "tenant_id": incident.tenant_id})

        if len(name) > max_name_length:
            logger.info(f"Generated incident name is too long. Applying smart truncation",
                        extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})

            name = client.chat.completions.create(model=model, messages=[
                {
                    "role": "system",
                    "content": f"""You are a very skilled DevOps specialist who can name any incident based on a description.  
                    Add information about start time to the name.When provided with information, answer with max a 
                    {int(max_name_length * 0.9)} symbols.
                    
                    EXAMPLE:
                    Kubernetes rollout stuck (started on 2022.11.17 14:11)"""
                },
                {
                    "role": "user",
                    "content": f"""This incident started on {incident_start}.
                    Here is the description of an incident to name:\n{name}."""
                }
            ]).choices[0].message.content

            logger.info(f"Generated new incident name with length {len(name)} symbols",
                        extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})

            if len(name) > max_name_length:
                logger.info(f"Generated incident name is too long. Applying hard truncation",
                            extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})
                name = name[: max_name_length]

        return name
    except Exception as e:
        logger.error(f"Error in generating incident name: {e}",
                     extra={"algorithm": NAME_GENERATOR_VERBOSE_NAME, "incident_id": incident.id, "tenant_id": incident.tenant_id})
        return ""
