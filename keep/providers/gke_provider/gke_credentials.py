from google.auth import default as google_auth_default
from google.oauth2 import service_account

GKE_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def build_gke_credentials(service_account_data=None, project_id=None):
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

    credentials, default_project = google_auth_default(scopes=GKE_SCOPES)
    return credentials, project_id or default_project
