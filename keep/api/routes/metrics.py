import chevron

from fastapi import Query
from typing import List
from fastapi import APIRouter, Depends, Response

from keep.api.models.alert import AlertDto
from keep.api.core.db import get_last_incidents, get_last_alerts_for_incidents
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


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
    - open_incidents_total - The total number of open incidents

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
      # Check Keep -> Feed -> "extraPayload" column.

      params:
        labels: ['labels.service', 'labels.queue']
      # Will resuld as: "labels_service" and "labels_queue".
    ```
    """
    # We don't use im-memory metrics countrs here which is typical for prometheus exporters,
    # they would make us expose our app's pod id's. This is a customer-facing endpoing
    # we're deploying to SaaS, and we want to hide our internal infra.

    tenant_id = authenticated_entity.tenant_id

    export = str()

    # Exporting alerts per incidents
    export += "# HELP alerts_total The total number of alerts per incident.\n"
    export += "# TYPE alerts_total counter\n"
    incidents, incidents_total = get_last_incidents(
        tenant_id=tenant_id,
        limit=1000,
        is_confirmed=True,
    )

    last_alerts_for_incidents = get_last_alerts_for_incidents([incident.id for incident in incidents])
    
    for incident in incidents:
        incident_name = incident.user_generated_name if incident.user_generated_name else incident.ai_generated_name
        extra_labels = ""
        try:
            last_alert = last_alerts_for_incidents[str(incident.id)][0]
            last_alert_dto = AlertDto(**last_alert.event)
        except IndexError:
            last_alert_dto = None

        for label in labels:
            label_value = chevron.render("{{ " + label + " }}", last_alert_dto)
            if label_value is None:
                label_value = "None"
            label = label.replace(".", "_")
            extra_labels += f' {label}="{label_value}"'
        export += f'alerts_total{{incident_name="{incident_name}" incident_id="{incident.id}"{extra_labels}}} {incident.alerts_count}\n'
    
    # Exporting stats about open incidents
    export += "\n\n"
    export += "# HELP open_incidents_total The total number of open incidents.\r\n"
    export += "# TYPE open_incidents_total counter\n"
    export += f"open_incidents_total {incidents_total}\n"

    return Response(content=export, media_type=CONTENT_TYPE_LATEST)
