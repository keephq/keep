import json
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import DefaultCredentialsError

from keep.providers.gke_provider.gke_credentials import (
    build_gke_credentials,
    resolve_service_account,
)

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


def test_build_gke_credentials_clear_error_when_no_adc():
    with patch(
        f"{MODULE}.google_auth_default",
        side_effect=DefaultCredentialsError("raw"),
    ):
        with pytest.raises(
            DefaultCredentialsError, match="No service account JSON provided"
        ):
            build_gke_credentials(None)


def test_resolve_parses_json_and_project():
    data = {"project_id": "sa-project"}
    parsed, project_id = resolve_service_account(json.dumps(data))
    assert parsed == data
    assert project_id == "sa-project"


def test_resolve_empty_json_returns_none():
    assert resolve_service_account("") == (None, None)


def test_resolve_explicit_project_overrides_sa_project():
    data = {"project_id": "sa-project"}
    parsed, project_id = resolve_service_account(
        json.dumps(data), project_id="explicit"
    )
    assert parsed == data
    assert project_id == "explicit"


def test_resolve_malformed_json_warns_and_falls_back():
    logger = MagicMock()
    parsed, project_id = resolve_service_account("{not-json", logger=logger)
    assert parsed is None
    assert project_id is None
    logger.warning.assert_called_once()


def test_resolve_malformed_json_keeps_explicit_project():
    parsed, project_id = resolve_service_account("{not-json", project_id="explicit")
    assert parsed is None
    assert project_id == "explicit"
