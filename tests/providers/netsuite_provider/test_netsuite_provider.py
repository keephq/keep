"""
Tests for NetSuiteProvider.

Covers:
- Auth header generation (NLAuth and TBA)
- validate_scopes success and failure paths
- get_support_cases (list, filter)
- get_support_case (single record)
- create_support_case (201/204/error)
- update_support_case (200/204/error)
- list_employees
- get_customer
- _notify() dispatch
- _query() dispatch
- dispose() no-op
- _use_tba() detection
- _nlauth_header() format
- _tba_header() signature structure
- _safe_ref() helper
- _rest_base property
- error and edge cases
"""

import json
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

# ---------------------------------------------------------------------------
# Patch heavy Keep internals before ANY keep.* import so the test module
# loads even without the full Keep application stack installed.
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    "keep.api",
    "keep.api.core",
    "keep.api.core.config",
    "keep.api.core.db",
    "keep.api.core.db_utils",
    "keep.api.core.dependencies",
    "keep.api.logging",
    "keep.api.bl",
    "keep.api.bl.enrichments_bl",
    "keep.api.bl.maintenance_windows_bl",
    "keep.api.models",
    "keep.api.models.action_type",
    "keep.api.models.alert",
    "keep.api.models.db",
    "keep.api.models.db.topology",
    "keep.api.models.incident",
    "keep.api.utils",
    "keep.api.utils.enrichment_helpers",
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.ext",
    "sqlalchemy.ext.declarative",
    "sqlalchemy.pool",
    "pymysql",
    "google",
    "google.cloud",
    "google.cloud.sql",
    "google.cloud.sql.connector",
    "pusher",
    "pydantic.v1",
    "json5",
    "pympler",
    "pympler.asizeof",
]

# Register as proper packages (with __path__) so submodule imports succeed.
for _mod in _STUB_MODULES:
    if _mod not in sys.modules:
        _mock_mod = MagicMock()
        _mock_mod.__path__ = []
        _mock_mod.__spec__ = None
        sys.modules[_mod] = _mock_mod

# Stub out TopologyServiceInDto and incident models so imports inside the provider work.
sys.modules["keep.api.models.db.topology"].TopologyServiceInDto = MagicMock
_inc = sys.modules["keep.api.models.incident"]
for _attr in ("IncidentDto", "IncidentStatus", "IncidentSeverity"):
    setattr(_inc, _attr, MagicMock)

# Now safe to import Keep classes.
from keep.contextmanager.contextmanager import ContextManager  # noqa: E402
from keep.providers.netsuite_provider.netsuite_provider import NetSuiteProvider  # noqa: E402
from keep.providers.models.provider_config import ProviderConfig  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_context() -> ContextManager:
    ctx = MagicMock(spec=ContextManager)
    ctx.tenant_id = "test-tenant"
    return ctx


def _nlauth_config(**overrides) -> ProviderConfig:
    """Return a ProviderConfig using NLAuth credentials."""
    auth = {
        "account_id": "1234567",
        "email": "admin@example.com",
        "password": "supersecret",
        "role_id": "3",
    }
    auth.update(overrides)
    return ProviderConfig(description="Test NetSuite", authentication=auth)


def _tba_config(**overrides) -> ProviderConfig:
    """Return a ProviderConfig using TBA credentials."""
    auth = {
        "account_id": "1234567",
        "consumer_key": "ck_test",
        "consumer_secret": "cs_test",
        "token_key": "tk_test",
        "token_secret": "ts_test",
    }
    auth.update(overrides)
    return ProviderConfig(description="Test NetSuite TBA", authentication=auth)


def _make_provider(config: ProviderConfig = None) -> NetSuiteProvider:
    if config is None:
        config = _nlauth_config()
    return NetSuiteProvider(
        context_manager=_make_context(),
        provider_id="netsuite_test",
        config=config,
    )


def _mock_response(
    status_code: int = 200,
    json_data: dict = None,
    text: str = "",
    headers: dict = None,
) -> MagicMock:
    """Build a mock requests.Response object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    resp.text = text or json.dumps(json_data or {})
    resp.content = resp.text.encode() if resp.text else b""
    resp.headers = headers or {}
    resp.json.return_value = json_data or {}
    return resp


# ---------------------------------------------------------------------------
# Instantiation / Config
# ---------------------------------------------------------------------------


class TestInstantiation:
    def test_nlauth_config_is_parsed(self):
        p = _make_provider(_nlauth_config())
        cfg = p.authentication_config
        assert cfg.account_id == "1234567"
        assert cfg.email == "admin@example.com"
        assert cfg.password == "supersecret"
        assert cfg.role_id == "3"

    def test_tba_config_is_parsed(self):
        p = _make_provider(_tba_config())
        cfg = p.authentication_config
        assert cfg.consumer_key == "ck_test"
        assert cfg.token_secret == "ts_test"

    def test_provider_id_is_stored(self):
        p = _make_provider()
        assert p.provider_id == "netsuite_test"

    def test_display_name(self):
        assert NetSuiteProvider.PROVIDER_DISPLAY_NAME == "NetSuite"

    def test_provider_category_includes_ticketing(self):
        assert "Ticketing" in NetSuiteProvider.PROVIDER_CATEGORY

    def test_provider_tags(self):
        assert "ticketing" in NetSuiteProvider.PROVIDER_TAGS

    def test_scopes_defined(self):
        scope_names = [s.name for s in NetSuiteProvider.PROVIDER_SCOPES]
        assert "rest_webservices" in scope_names
        assert "support_cases_read" in scope_names
        assert "support_cases_write" in scope_names

    def test_methods_defined(self):
        method_names = [m.func_name for m in NetSuiteProvider.PROVIDER_METHODS]
        assert "get_support_cases" in method_names
        assert "create_support_case" in method_names
        assert "update_support_case" in method_names
        assert "list_employees" in method_names
        assert "get_customer" in method_names

    def test_dispose_is_noop(self):
        p = _make_provider()
        p.dispose()  # Should not raise


# ---------------------------------------------------------------------------
# _use_tba()
# ---------------------------------------------------------------------------


class TestUseTba:
    def test_use_tba_false_when_only_nlauth(self):
        p = _make_provider(_nlauth_config())
        assert p._use_tba() is False

    def test_use_tba_true_when_tba_creds_set(self):
        p = _make_provider(_tba_config())
        assert p._use_tba() is True

    def test_use_tba_false_when_partial_tba(self):
        p = _make_provider(_tba_config(consumer_key="", token_key=""))
        assert p._use_tba() is False


# ---------------------------------------------------------------------------
# _rest_base property
# ---------------------------------------------------------------------------


class TestRestBase:
    def test_base_url_is_constructed_from_account_id(self):
        p = _make_provider(_nlauth_config(account_id="TSTDRV9876"))
        expected = "https://tstdrv9876.suitetalk.api.netsuite.com/services/rest"
        assert p._rest_base == expected

    def test_base_url_normalises_underscores(self):
        p = _make_provider(_nlauth_config(account_id="ORG_1234"))
        # underscores become hyphens in hostname
        assert "org-1234" in p._rest_base

    def test_base_url_is_cached(self):
        p = _make_provider()
        url1 = p._rest_base
        url2 = p._rest_base
        assert url1 is url2


# ---------------------------------------------------------------------------
# NLAuth header
# ---------------------------------------------------------------------------


class TestNlauthHeader:
    def test_header_contains_account_id(self):
        p = _make_provider(_nlauth_config(account_id="99999"))
        hdr = p._nlauth_header()
        assert "nlauth_account=99999" in hdr

    def test_header_contains_email(self):
        p = _make_provider()
        hdr = p._nlauth_header()
        assert "nlauth_email=admin@example.com" in hdr

    def test_header_contains_password(self):
        p = _make_provider()
        hdr = p._nlauth_header()
        assert "nlauth_signature=supersecret" in hdr

    def test_header_contains_role_when_set(self):
        p = _make_provider(_nlauth_config(role_id="5"))
        hdr = p._nlauth_header()
        assert "nlauth_role=5" in hdr

    def test_header_omits_role_when_empty(self):
        p = _make_provider(_nlauth_config(role_id=""))
        hdr = p._nlauth_header()
        assert "nlauth_role" not in hdr

    def test_header_starts_with_nlauth(self):
        p = _make_provider()
        hdr = p._nlauth_header()
        assert hdr.startswith("NLAuth ")


# ---------------------------------------------------------------------------
# TBA header
# ---------------------------------------------------------------------------


class TestTbaHeader:
    _TEST_URL = "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1/ping"

    def test_tba_header_starts_with_oauth(self):
        p = _make_provider(_tba_config())
        hdr = p._tba_header("GET", self._TEST_URL)
        assert hdr.startswith("OAuth ")

    def test_tba_header_contains_realm(self):
        p = _make_provider(_tba_config(account_id="ACME123"))
        hdr = p._tba_header("GET", self._TEST_URL)
        assert 'realm="ACME123"' in hdr

    def test_tba_header_contains_consumer_key(self):
        p = _make_provider(_tba_config())
        hdr = p._tba_header("GET", self._TEST_URL)
        assert "ck_test" in hdr

    def test_tba_header_contains_token_key(self):
        p = _make_provider(_tba_config())
        hdr = p._tba_header("GET", self._TEST_URL)
        assert "tk_test" in hdr

    def test_tba_header_contains_hmac_sha256(self):
        p = _make_provider(_tba_config())
        hdr = p._tba_header("POST", self._TEST_URL)
        assert "HMAC-SHA256" in hdr

    def test_tba_header_contains_oauth_signature(self):
        p = _make_provider(_tba_config())
        hdr = p._tba_header("GET", self._TEST_URL)
        assert "oauth_signature" in hdr


# ---------------------------------------------------------------------------
# _get_headers()
# ---------------------------------------------------------------------------


class TestGetHeaders:
    def test_nlauth_mode_uses_nlauth_header(self):
        p = _make_provider(_nlauth_config())
        hdrs = p._get_headers("GET", "https://example.com")
        assert hdrs["Authorization"].startswith("NLAuth")

    def test_tba_mode_uses_oauth_header(self):
        p = _make_provider(_tba_config())
        hdrs = p._get_headers("GET", "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1/ping")
        assert hdrs["Authorization"].startswith("OAuth")

    def test_content_type_is_json(self):
        p = _make_provider()
        hdrs = p._get_headers()
        assert hdrs["Content-Type"] == "application/json"

    def test_accept_is_json(self):
        p = _make_provider()
        hdrs = p._get_headers()
        assert hdrs["Accept"] == "application/json"


# ---------------------------------------------------------------------------
# _safe_ref()
# ---------------------------------------------------------------------------


class TestSafeRef:
    def test_extracts_ref_name_from_dict(self):
        result = NetSuiteProvider._safe_ref({"refName": "Open", "id": "1"})
        assert result == "Open"

    def test_falls_back_to_id_when_no_refname(self):
        result = NetSuiteProvider._safe_ref({"id": "42"})
        assert result == "42"

    def test_returns_string_for_plain_value(self):
        result = NetSuiteProvider._safe_ref("plain_string")
        assert result == "plain_string"

    def test_returns_empty_string_for_none(self):
        result = NetSuiteProvider._safe_ref(None)
        assert result == ""

    def test_returns_string_for_integer(self):
        result = NetSuiteProvider._safe_ref(42)
        assert result == "42"


# ---------------------------------------------------------------------------
# validate_scopes
# ---------------------------------------------------------------------------


class TestValidateScopes:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.get")
    def test_all_scopes_true_on_success(self, mock_get):
        ping_resp = _mock_response(200, {})
        cases_resp = _mock_response(200, {"items": []})
        mock_get.side_effect = [ping_resp, cases_resp]

        p = _make_provider()
        scopes = p.validate_scopes()

        assert scopes["rest_webservices"] is True
        assert scopes["support_cases_read"] is True

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.get")
    def test_401_marks_rest_webservices_as_auth_error(self, mock_get):
        mock_get.return_value = _mock_response(401, {}, text="Unauthorized")

        p = _make_provider()
        scopes = p.validate_scopes()

        assert "Authentication failed" in scopes["rest_webservices"]

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.get")
    def test_403_marks_rest_webservices_as_forbidden(self, mock_get):
        mock_get.return_value = _mock_response(403, {}, text="Forbidden")

        p = _make_provider()
        scopes = p.validate_scopes()

        assert "Forbidden" in scopes["rest_webservices"]

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.get")
    def test_connection_error_returns_error_message(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("timeout")

        p = _make_provider()
        scopes = p.validate_scopes()

        assert "Cannot connect" in scopes["rest_webservices"]

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.get")
    def test_500_returns_status_in_message(self, mock_get):
        mock_get.return_value = _mock_response(500, {}, text="Internal Server Error")

        p = _make_provider()
        scopes = p.validate_scopes()

        assert "500" in scopes["rest_webservices"]

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.get")
    def test_cases_403_marks_read_as_no_permission(self, mock_get):
        ping_resp = _mock_response(200, {})
        cases_resp = _mock_response(403, {}, text="Forbidden")
        mock_get.side_effect = [ping_resp, cases_resp]

        p = _make_provider()
        scopes = p.validate_scopes()

        assert scopes["rest_webservices"] is True
        assert "No permission" in scopes["support_cases_read"]


# ---------------------------------------------------------------------------
# get_support_cases
# ---------------------------------------------------------------------------


class TestGetSupportCases:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_list_of_cases(self, mock_req):
        cases = [
            {"id": "1", "title": "Case A"},
            {"id": "2", "title": "Case B"},
        ]
        mock_req.return_value = _mock_response(200, {"items": cases})

        p = _make_provider()
        result = p.get_support_cases(limit=10)

        assert len(result) == 2
        assert result[0]["title"] == "Case A"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_empty_list_on_error(self, mock_req):
        mock_req.return_value = _mock_response(500, {}, text="Error")

        p = _make_provider()
        result = p.get_support_cases()

        assert result == []

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_passes_limit_param(self, mock_req):
        mock_req.return_value = _mock_response(200, {"items": []})

        p = _make_provider()
        p.get_support_cases(limit=25)

        assert mock_req.called

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_handles_missing_items_key(self, mock_req):
        mock_req.return_value = _mock_response(200, {})

        p = _make_provider()
        result = p.get_support_cases()

        assert result == []

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_applies_status_filter(self, mock_req):
        mock_req.return_value = _mock_response(200, {"items": []})

        p = _make_provider()
        p.get_support_cases(status_filter="1")

        assert mock_req.called

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_applies_priority_filter(self, mock_req):
        mock_req.return_value = _mock_response(200, {"items": []})

        p = _make_provider()
        p.get_support_cases(priority_filter="2")

        assert mock_req.called

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_all_cases_from_response(self, mock_req):
        cases = [{"id": str(i)} for i in range(5)]
        mock_req.return_value = _mock_response(200, {"items": cases})

        p = _make_provider()
        result = p.get_support_cases()

        assert len(result) == 5


# ---------------------------------------------------------------------------
# get_support_case
# ---------------------------------------------------------------------------


class TestGetSupportCase:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_case_dict(self, mock_req):
        case = {"id": "42", "title": "Test Case", "status": {"refName": "Open"}}
        mock_req.return_value = _mock_response(200, case)

        p = _make_provider()
        result = p.get_support_case("42")

        assert result["id"] == "42"
        assert result["title"] == "Test Case"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_empty_dict_on_404(self, mock_req):
        mock_req.return_value = _mock_response(404, {}, text="Not Found")

        p = _make_provider()
        result = p.get_support_case("999")

        assert result == {}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_request_is_made(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "77"})

        p = _make_provider()
        p.get_support_case("77")

        assert mock_req.called


# ---------------------------------------------------------------------------
# create_support_case
# ---------------------------------------------------------------------------


class TestCreateSupportCase:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_dict_with_id_on_204(self, mock_req):
        resp = _mock_response(
            204, {},
            headers={"Location": "https://1234567.suitetalk.api.netsuite.com/services/rest/record/v1/supportcase/999"}
        )
        resp.content = b""
        mock_req.return_value = resp

        p = _make_provider()
        result = p.create_support_case("Bug in module X", description="Details")

        assert result["id"] == "999"
        assert "link" in result

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_json_on_200(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "100", "title": "New case"})

        p = _make_provider()
        result = p.create_support_case("New case")

        assert result["id"] == "100"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_raises_provider_exception_on_error(self, mock_req):
        mock_req.return_value = _mock_response(400, {}, text="Bad Request")

        p = _make_provider()
        with pytest.raises(Exception):
            p.create_support_case("bad payload")

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_payload_contains_title(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Critical outage")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("title") == "Critical outage"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_payload_contains_description(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Title", description="Details here")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("incomingMessage") == "Details here"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_payload_includes_customer_id(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Title", customer_id="555")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("company") == {"id": "555"}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_payload_includes_assigned_to(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Title", assigned_to="emp_123")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("assigned") == {"id": "emp_123"}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_default_priority_is_medium(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Title")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("priority") == {"id": "3"}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_default_status_is_open(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Title")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("status") == {"id": "1"}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_custom_priority_is_passed(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Urgent!", priority="1")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("priority") == {"id": "1"}


# ---------------------------------------------------------------------------
# update_support_case
# ---------------------------------------------------------------------------


class TestUpdateSupportCase:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_dict_on_200(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "42", "updated": True})

        p = _make_provider()
        result = p.update_support_case("42", status="5")

        assert result["id"] == "42"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_dict_on_204(self, mock_req):
        resp = _mock_response(204, {})
        resp.content = b""
        mock_req.return_value = resp

        p = _make_provider()
        result = p.update_support_case("42", priority="2")

        assert result["updated"] is True

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_raises_when_no_fields_provided(self, mock_req):
        p = _make_provider()
        with pytest.raises(Exception):
            p.update_support_case("42")

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_raises_on_error_response(self, mock_req):
        mock_req.return_value = _mock_response(404, {}, text="Not Found")

        p = _make_provider()
        with pytest.raises(Exception):
            p.update_support_case("42", status="6")

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_status_field_in_payload(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "42"})

        p = _make_provider()
        p.update_support_case("42", status="6")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("status") == {"id": "6"}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_reply_message_in_payload(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "42"})

        p = _make_provider()
        p.update_support_case("42", reply_message="Resolved in v2.3")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("outgoingMessage") == "Resolved in v2.3"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_uses_patch_method(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "42"})

        p = _make_provider()
        p.update_support_case("42", status="5")

        # The method argument is passed as keyword
        called_method = mock_req.call_args[1].get("method") or (
            mock_req.call_args[0][0] if mock_req.call_args[0] else ""
        )
        assert called_method.upper() == "PATCH"


# ---------------------------------------------------------------------------
# list_employees
# ---------------------------------------------------------------------------


class TestListEmployees:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_list(self, mock_req):
        employees = [{"id": "1", "entityId": "Alice"}, {"id": "2", "entityId": "Bob"}]
        mock_req.return_value = _mock_response(200, {"items": employees})

        p = _make_provider()
        result = p.list_employees()

        assert len(result) == 2
        assert result[0]["entityId"] == "Alice"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_empty_on_error(self, mock_req):
        mock_req.return_value = _mock_response(403, {}, text="Forbidden")

        p = _make_provider()
        result = p.list_employees()

        assert result == []

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_handles_missing_items_key(self, mock_req):
        mock_req.return_value = _mock_response(200, {})

        p = _make_provider()
        result = p.list_employees()

        assert result == []


# ---------------------------------------------------------------------------
# get_customer
# ---------------------------------------------------------------------------


class TestGetCustomer:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_customer_dict(self, mock_req):
        customer = {"id": "333", "companyName": "Acme Corp"}
        mock_req.return_value = _mock_response(200, customer)

        p = _make_provider()
        result = p.get_customer("333")

        assert result["companyName"] == "Acme Corp"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_returns_empty_on_404(self, mock_req):
        mock_req.return_value = _mock_response(404, {}, text="Not Found")

        p = _make_provider()
        result = p.get_customer("999")

        assert result == {}


# ---------------------------------------------------------------------------
# _notify() and _query()
# ---------------------------------------------------------------------------


class TestNotifyAndQuery:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_notify_calls_create_support_case(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p._notify(title="Alert fired", description="CPU > 90%", priority="2")

        assert mock_req.called
        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("title") == "Alert fired"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_query_delegates_to_get_support_cases(self, mock_req):
        cases = [{"id": "1"}, {"id": "2"}]
        mock_req.return_value = _mock_response(200, {"items": cases})

        p = _make_provider()
        result = p._query(limit=10)

        assert len(result) == 2

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_notify_passes_customer_id(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p._notify(title="Test", customer_id="cust_999")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("company") == {"id": "cust_999"}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_notify_passes_assigned_to(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p._notify(title="Test", assigned_to="emp_777")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("assigned") == {"id": "emp_777"}

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_notify_with_high_priority(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/99"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p._notify(title="Critical", priority="1")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json["priority"] == {"id": "1"}


# ---------------------------------------------------------------------------
# Status / priority constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_status_map_has_open(self):
        assert "1" in NetSuiteProvider.STATUS_MAP
        assert NetSuiteProvider.STATUS_MAP["1"] == "open"

    def test_status_map_has_resolved(self):
        assert "5" in NetSuiteProvider.STATUS_MAP
        assert NetSuiteProvider.STATUS_MAP["5"] == "resolved"

    def test_priority_map_has_critical(self):
        assert "1" in NetSuiteProvider.PRIORITY_MAP
        assert NetSuiteProvider.PRIORITY_MAP["1"] == "critical"

    def test_priority_map_has_low(self):
        assert "4" in NetSuiteProvider.PRIORITY_MAP
        assert NetSuiteProvider.PRIORITY_MAP["4"] == "low"

    def test_status_map_has_closed(self):
        assert "6" in NetSuiteProvider.STATUS_MAP
        assert NetSuiteProvider.STATUS_MAP["6"] == "closed"

    def test_priority_map_has_medium(self):
        assert "3" in NetSuiteProvider.PRIORITY_MAP
        assert NetSuiteProvider.PRIORITY_MAP["3"] == "medium"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_create_case_with_extra_kwargs(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Title", custom_field="value123")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("custom_field") == "value123"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_update_case_with_extra_kwargs(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "42"})

        p = _make_provider()
        p.update_support_case("42", status="3", custom_note="extra info")

        call_json = mock_req.call_args[1].get("json", {})
        assert call_json.get("custom_note") == "extra info"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_get_cases_returns_empty_when_items_missing(self, mock_req):
        mock_req.return_value = _mock_response(200, {"total": 0})

        p = _make_provider()
        result = p.get_support_cases()

        assert result == []

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_create_case_204_with_no_location_header(self, mock_req):
        resp = _mock_response(204, {}, headers={})
        resp.content = b""
        mock_req.return_value = resp

        p = _make_provider()
        result = p.create_support_case("Headless case")

        # id falls back to "unknown" when no Location header
        assert result["id"] == "unknown"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.get")
    def test_validate_scopes_handles_generic_exception(self, mock_get):
        mock_get.side_effect = Exception("Unexpected error")

        p = _make_provider()
        scopes = p.validate_scopes()

        assert "rest_webservices" in scopes
        # Should contain the error message, not crash
        assert scopes["rest_webservices"] != True  # noqa: E712

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_create_case_uses_post_method(self, mock_req):
        mock_req.return_value = _mock_response(204, {}, headers={"Location": "/1"})
        mock_req.return_value.content = b""

        p = _make_provider()
        p.create_support_case("Test POST")

        called_method = mock_req.call_args[1].get("method") or (
            mock_req.call_args[0][0] if mock_req.call_args[0] else ""
        )
        assert called_method.upper() == "POST"

    @patch("keep.providers.netsuite_provider.netsuite_provider.requests.request")
    def test_get_support_case_uses_get_method(self, mock_req):
        mock_req.return_value = _mock_response(200, {"id": "5"})

        p = _make_provider()
        p.get_support_case("5")

        called_method = mock_req.call_args[1].get("method") or (
            mock_req.call_args[0][0] if mock_req.call_args[0] else ""
        )
        assert called_method.upper() == "GET"
