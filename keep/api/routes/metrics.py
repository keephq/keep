from fastapi import APIRouter, Depends, Response

from keep.api.core.db import get_last_incidents
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.identitymanagerfactory import IdentityManagerFactory

router = APIRouter()

CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"


@router.get("")
def get_metrics(
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
    for incident in incidents:
        export += f'alerts_total{{incident_name="{incident.name}" incident_id="{incident.id}"}} {incident.alerts_count}\n'

    # Exporting stats about open incidents
    export += "\n\n"
    export += "# HELP open_incidents_total The total number of open incidents.\r\n"
    export += "# TYPE open_incidents_total counter\n"
    export += f"open_incidents_total {incidents_total}\n"

    return Response(content=export, media_type=CONTENT_TYPE_LATEST)
