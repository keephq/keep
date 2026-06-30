import json

from google.auth import default as google_auth_default
from google.auth.credentials import Credentials
from google.auth.exceptions import DefaultCredentialsError
from google.oauth2 import service_account

GKE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def resolve_service_account(
    service_account_json: str | None,
    project_id: str | None = None,
    logger=None,
) -> tuple[dict | None, str | None]:
    """Parse the optional service account JSON and resolve the project id.

    Returns (service_account_data, project_id). When the JSON is empty or cannot
    be parsed the data is None so the caller falls back to Application Default
    Credentials; a malformed JSON is logged so the fallback is observable.
    """
    resolved_project = project_id or None
    if not service_account_json:
        return None, resolved_project
    try:
        data = json.loads(service_account_json)
    except Exception:
        if logger is not None:
            logger.warning(
                "Invalid service_account_json provided, falling back to "
                "Application Default Credentials"
            )
        return None, resolved_project
    return data, resolved_project or data.get("project_id")


def build_gke_credentials(
    service_account_data: dict | None = None,
    project_id: str | None = None,
) -> tuple[Credentials, str | None]:
    """Return (credentials, project_id) for accessing a GKE cluster.

    When a service account JSON is supplied its credentials are used directly.
    Otherwise the environment's Application Default Credentials are used (for
    example a GKE Workload Identity service account), which also resolves the
    project when it is not provided explicitly.
    """
    if service_account_data:
        credentials = service_account.Credentials.from_service_account_info(
            service_account_data, scopes=GKE_SCOPES
        )
        return credentials, project_id or service_account_data.get("project_id")

    try:
        credentials, default_project = google_auth_default(scopes=GKE_SCOPES)
    except DefaultCredentialsError as exc:
        raise DefaultCredentialsError(
            "No service account JSON provided and no Application Default Credentials found"
        ) from exc
    return credentials, project_id or default_project
