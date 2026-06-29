from unittest.mock import patch

from keep.providers.gke_provider.gke_credentials import build_gke_credentials

MODULE = "keep.providers.gke_provider.gke_credentials"


def test_uses_service_account_when_json_provided():
    data = {"project_id": "sa-project", "client_email": "x@y.iam"}
    with (
        patch(f"{MODULE}.service_account") as mock_sa,
        patch(f"{MODULE}.google_auth_default") as mock_default,
    ):
        credentials, project_id = build_gke_credentials(data)
        mock_sa.Credentials.from_service_account_info.assert_called_once()
        mock_default.assert_not_called()
        assert project_id == "sa-project"
        assert credentials is mock_sa.Credentials.from_service_account_info.return_value


def test_falls_back_to_adc_when_no_service_account():
    with (
        patch(f"{MODULE}.service_account") as mock_sa,
        patch(
            f"{MODULE}.google_auth_default",
            return_value=("adc-creds", "adc-project"),
        ) as mock_default,
    ):
        credentials, project_id = build_gke_credentials(None)
        mock_default.assert_called_once()
        mock_sa.Credentials.from_service_account_info.assert_not_called()
        assert credentials == "adc-creds"
        assert project_id == "adc-project"


def test_explicit_project_id_overrides_adc():
    with patch(f"{MODULE}.google_auth_default", return_value=("c", "adc-project")):
        _, project_id = build_gke_credentials(None, project_id="explicit")
        assert project_id == "explicit"


def test_service_account_project_used_when_no_explicit_project():
    data = {"project_id": "sa-project"}
    with patch(f"{MODULE}.service_account"):
        _, project_id = build_gke_credentials(data, project_id="")
        assert project_id == "sa-project"
