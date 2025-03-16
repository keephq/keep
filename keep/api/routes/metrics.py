from typing import List

import chevron
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    generate_latest,
    multiprocess,
)

from keep.api.core.config import config
from keep.api.core.db import (
    get_last_alerts_for_incidents,
    get_last_incidents,
    get_workflow_executions_count,
)
from keep.api.core.limiter import limiter
from keep.api.models.alert import AlertDto
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
NO_AUTH_METRICS = config("KEEP_NO_AUTH_METRICS", default=False, cast=bool)

if NO_AUTH_METRICS:

    @router.get("/processing", include_in_schema=False)
    async def get_processing_metrics(
        request: Request,
    ):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        metrics = generate_latest(registry)
        return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)

else:

    @router.get("/processing", include_in_schema=False)
    async def get_processing_metrics(
        request: Request,
        authenticated_entity: AuthenticatedEntity = Depends(
            IdentityManagerFactory.get_auth_verifier(["read:metrics"])
        ),
    ):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        metrics = generate_latest(registry)
        return Response(content=metrics, media_type=CONTENT_TYPE_LATEST)


@router.get("")
def get_metrics(
    labels: List[str] = Query(None),
    authenticated_entity: AuthenticatedEntity = Depends(
        IdentityManagerFactory.get_auth_verifier(["read:metrics"])
    ),
):
    """
    This endpoint is used by Prometheus to scrape such metrics from the application:
    - alerts_total {incident_name, incident_id} - The total number of alerts per incident.
    - open_incidents_total - The total number of open incidents.
    - workflows_executions_total {status} - The total number of workflow executions.

    Please note that those metrics are per-tenant and are not designed to be used for the monitoring of the application itself.

    Example prometheus configuration:
    ```
    scrape_configs:
    - job_name: "scrape_keep"
      scrape_interval: 5m  # It's important to scrape not too often to avoid rate limiting.
      static_configs:
      - targets: ["https://api.keephq.dev"]  # Or your own domain.
      authorization:
        type: Bearer
        credentials: "{Your API Key}"

      # Optional, you can add labels to exported incidents.
      # Label values will be equal to the last incident's alert payload value matching the label.
      # Attention! Don't add "flaky" labels which could change from alert to alert within the same incident.
      # Good labels: ['labels.department', 'labels.team'], bad labels: ['labels.severity', 'labels.pod_id']
      # Check Keep -> Feed -> "extraPayload" column, it will help in writing labels.

      params:
        labels: ['labels.service', 'labels.queue']
      # Will resuld as: "labels_service" and "labels_queue".
    ```
    """
    # We don't use im-memory metrics countrs here which is typical for prometheus exporters,
    # they would make us expose our app's pod id's. This is a customer-facing endpoint
    # we're deploying to SaaS, and we want to hide our internal infra.

    tenant_id = authenticated_entity.tenant_id

    export = str()

    # Exporting alerts per incidents
    export += "# HELP alerts_total The total number of alerts per incident.\n"
    export += "# TYPE alerts_total counter\n"
    incidents, incidents_total = get_last_incidents(
        tenant_id=tenant_id,
        limit=1000,
        is_candidate=False,
    )

    last_alerts_for_incidents = get_last_alerts_for_incidents(
        [incident.id for incident in incidents]
    )

    for incident in incidents:
        incident_name = (
            incident.user_generated_name
            if incident.user_generated_name
            else incident.ai_generated_name
        )
        extra_labels = ""
        try:
            last_alert = last_alerts_for_incidents[str(incident.id)][0]
            last_alert_dto = AlertDto(**last_alert.event)
        except IndexError:
            last_alert_dto = None

        if labels is not None:
            for label in labels:
                label_value = chevron.render("{{ " + label + " }}", last_alert_dto)
                label = label.replace(".", "_")
                extra_labels += f',{label}="{label_value}"'

        export += f'alerts_total{{incident_name="{incident_name}",incident_id="{incident.id}"{extra_labels}}} {incident.alerts_count}\n'

    # Exporting stats about open incidents
    export += "\n\n"
    export += "# HELP open_incidents_total The total number of open incidents.\r\n"
    export += "# TYPE open_incidents_total counter\n"
    export += f"open_incidents_total {incidents_total}\n"

    workflow_execution_counts = get_workflow_executions_count(
        tenant_id=tenant_id,
    )

    export += "\n\n"
    export += "# HELP workflows_executions_total The total number of workflows.\r\n"
    export += "# TYPE workflows_executions_total counter\n"
    export += f"workflows_executions_total {{status=\"success\"}} {workflow_execution_counts['success']}\n"
    export += f"workflows_executions_total {{status=\"other\"}} {workflow_execution_counts['other']}\n"

    return Response(content=export, media_type=CONTENT_TYPE_LATEST)


@router.get("/dumb", include_in_schema=False)
@limiter.limit(config("KEEP_LIMIT_CONCURRENCY", default="10/minute", cast=str))
async def get_dumb(request: Request) -> JSONResponse:
    """
    This endpoint is used to test the rate limiting.

    Args:
        request (Request): The request object.

    Returns:
        JSONResponse: A JSON response with the message "hello world" ({"hello": "world"}).
    """
    # await asyncio.sleep(5)
    return JSONResponse(content={"hello": "world"})
