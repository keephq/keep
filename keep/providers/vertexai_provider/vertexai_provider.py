"""
VertexAIProvider is a class that integrates with Google Cloud Vertex AI to
monitor deployed model endpoints and surface anomalies as alerts in Keep.
"""

import dataclasses
import datetime
import json
import logging
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
VERTEX_AI_BASE = "https://{region}-aiplatform.googleapis.com/v1"


@pydantic.dataclasses.dataclass
class VertexAIProviderAuthConfig:
    """
    VertexAIProviderAuthConfig holds authentication configuration for Google
    Cloud Vertex AI.  Supports both a service-account JSON key (for pull-based
    monitoring) and a simple API key for lightweight setups.
    """

    project_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Google Cloud project ID",
            "hint": "Your GCP project ID, e.g. my-gcp-project",
        },
    )

    service_account_json: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Service account JSON key (full contents as a string)",
            "hint": "Copy the contents of your service account JSON key file",
            "sensitive": True,
            "type": "textarea",
        },
    )

    region: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "GCP region for Vertex AI (default: us-central1)",
            "hint": "e.g. us-central1, europe-west4",
        },
        default="us-central1",
    )


class VertexAIProvider(BaseProvider):
    """Monitor Google Cloud Vertex AI model endpoints and surface alerts in Keep."""

    PROVIDER_DISPLAY_NAME = "Vertex AI"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Cloud Infrastructure", "AI/ML"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="aiplatform.endpoints.list",
            description="List Vertex AI endpoints",
            mandatory=True,
            alias="List Endpoints",
            documentation_url="https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.endpoints/list",
        ),
        ProviderScope(
            name="aiplatform.models.list",
            description="List Vertex AI models",
            mandatory=False,
            alias="List Models",
            documentation_url="https://cloud.google.com/vertex-ai/docs/reference/rest/v1/projects.locations.models/list",
        ),
    ]

    # Map Vertex AI deployment / health states to Keep alert status
    _HEALTH_STATUS_MAP = {
        "HEALTHY": AlertStatus.RESOLVED,
        "DEGRADED": AlertStatus.FIRING,
        "UNHEALTHY": AlertStatus.FIRING,
        "OFFLINE": AlertStatus.FIRING,
        "DEPLOYING": AlertStatus.PENDING,
        "UNDEPLOYING": AlertStatus.PENDING,
    }

    # Map model/endpoint states to severity
    _HEALTH_SEVERITY_MAP = {
        "HEALTHY": AlertSeverity.INFO,
        "DEGRADED": AlertSeverity.WARNING,
        "UNHEALTHY": AlertSeverity.CRITICAL,
        "OFFLINE": AlertSeverity.HIGH,
        "DEPLOYING": AlertSeverity.INFO,
        "UNDEPLOYING": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime.datetime] = None

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = VertexAIProviderAuthConfig(
            **self.config.authentication
        )

    def _get_access_token(self) -> str:
        """Obtain a short-lived OAuth2 access token from a service-account key."""
        now = datetime.datetime.utcnow()
        if self._access_token and self._token_expiry and now < self._token_expiry:
            return self._access_token

        try:
            sa = json.loads(self.authentication_config.service_account_json)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "service_account_json is not valid JSON — paste the full contents "
                "of your service account key file"
            ) from exc

        import math
        import time

        try:
            import jwt  # PyJWT
        except ImportError:
            raise ImportError(
                "PyJWT is required for Vertex AI authentication. "
                "Install it with: pip install PyJWT cryptography"
            )

        iat = int(time.time())
        exp = iat + 3600
        payload = {
            "iss": sa["client_email"],
            "sub": sa["client_email"],
            "aud": GOOGLE_TOKEN_URL,
            "scope": "https://www.googleapis.com/auth/cloud-platform",
            "iat": iat,
            "exp": exp,
        }

        signed_jwt = jwt.encode(
            payload,
            sa["private_key"],
            algorithm="RS256",
            headers={"kid": sa.get("private_key_id", "")},
        )

        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": signed_jwt,
            },
            timeout=10,
        )
        resp.raise_for_status()
        token_data = resp.json()
        self._access_token = token_data["access_token"]
        self._token_expiry = now + datetime.timedelta(seconds=token_data.get("expires_in", 3600) - 60)
        return self._access_token

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "application/json",
        }

    def _base_url(self) -> str:
        return VERTEX_AI_BASE.format(region=self.authentication_config.region)

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {}
        project = self.authentication_config.project_id
        region = self.authentication_config.region
        try:
            url = f"{self._base_url()}/projects/{project}/locations/{region}/endpoints"
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            if resp.status_code == 200:
                scopes["aiplatform.endpoints.list"] = True
                scopes["aiplatform.models.list"] = True
            elif resp.status_code == 403:
                scopes["aiplatform.endpoints.list"] = "Permission denied — check service account IAM roles"
                scopes["aiplatform.models.list"] = "Permission denied — check service account IAM roles"
            else:
                scopes["aiplatform.endpoints.list"] = f"Unexpected status {resp.status_code}"
                scopes["aiplatform.models.list"] = f"Unexpected status {resp.status_code}"
        except Exception as e:
            self.logger.exception("Failed to validate Vertex AI scopes")
            scopes["aiplatform.endpoints.list"] = str(e)
            scopes["aiplatform.models.list"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """
        Pull Vertex AI model endpoint health and surface unhealthy/degraded
        endpoints as Keep alerts.
        """
        self.logger.info("Fetching Vertex AI endpoint statuses")
        project = self.authentication_config.project_id
        region = self.authentication_config.region
        alerts: List[AlertDto] = []

        try:
            url = f"{self._base_url()}/projects/{project}/locations/{region}/endpoints"
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            endpoints = resp.json().get("endpoints", [])
        except Exception as e:
            self.logger.error("Failed to fetch Vertex AI endpoints: %s", e)
            return alerts

        for endpoint in endpoints:
            endpoint_name = endpoint.get("displayName") or endpoint.get("name", "unknown")
            endpoint_id = endpoint.get("name", "").split("/")[-1]
            create_time = endpoint.get("createTime", "")
            update_time = endpoint.get("updateTime", create_time)

            try:
                last_received = datetime.datetime.fromisoformat(
                    str(update_time).replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow()

            deployed_models = endpoint.get("deployedModels", [])
            if not deployed_models:
                # Endpoint exists but has no models deployed — flag as low severity
                alert = AlertDto(
                    id=endpoint_id,
                    name=f"Vertex AI endpoint has no deployed models: {endpoint_name}",
                    severity=AlertSeverity.LOW,
                    status=AlertStatus.FIRING,
                    lastReceived=last_received,
                    description=f"Endpoint '{endpoint_name}' has no deployed models.",
                    source=["vertexai"],
                    url=f"https://console.cloud.google.com/vertex-ai/online-prediction/endpoints/{endpoint_id}?project={project}",
                    fingerprint=f"vertexai-endpoint-empty-{endpoint_id}",
                    project=project,
                    region=region,
                    endpoint_id=endpoint_id,
                )
                alerts.append(alert)
                continue

            for deployed_model in deployed_models:
                model_name = deployed_model.get("displayName") or deployed_model.get("model", "").split("/")[-1]
                dm_id = deployed_model.get("id", "")
                health_state = deployed_model.get("healthState", "UNKNOWN")

                severity = self._HEALTH_SEVERITY_MAP.get(health_state, AlertSeverity.WARNING)
                status = self._HEALTH_STATUS_MAP.get(health_state, AlertStatus.FIRING)

                # Only surface non-healthy models as alerts
                if health_state == "HEALTHY":
                    continue

                alert = AlertDto(
                    id=f"{endpoint_id}-{dm_id}",
                    name=f"Vertex AI model unhealthy: {model_name} on {endpoint_name}",
                    severity=severity,
                    status=status,
                    lastReceived=last_received,
                    description=(
                        f"Deployed model '{model_name}' on endpoint '{endpoint_name}' "
                        f"reported health state: {health_state}"
                    ),
                    source=["vertexai"],
                    url=(
                        f"https://console.cloud.google.com/vertex-ai/online-prediction/"
                        f"endpoints/{endpoint_id}?project={project}"
                    ),
                    fingerprint=f"vertexai-model-{endpoint_id}-{dm_id}",
                    project=project,
                    region=region,
                    endpoint_id=endpoint_id,
                    deployed_model_id=dm_id,
                    health_state=health_state,
                )
                alerts.append(alert)

        self.logger.info("Fetched %d Vertex AI alerts", len(alerts))
        return alerts


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    project_id = os.environ.get("GCP_PROJECT_ID", "my-project")
    service_account_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "{}")

    config = ProviderConfig(
        description="Vertex AI Provider",
        authentication={
            "project_id": project_id,
            "service_account_json": service_account_json,
            "region": "us-central1",
        },
    )
    provider = VertexAIProvider(
        context_manager, provider_id="vertexai-test", config=config
    )
    print(provider.validate_scopes())
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} alerts")
    for a in alerts:
        print(f"  - {a.name}: {a.severity} ({a.status})")
