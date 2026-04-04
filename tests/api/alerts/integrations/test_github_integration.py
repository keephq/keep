import pytest
import hmac
import hashlib
import json
import os
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from keep.alerts.base.alert import AlertDto, AlertStatus, AlertSeverity
from keep.api.alerts.integrations.github import router, verify_signature, _github_event_to_alert, DEFAULT_GITHUB_TENANT_ID

# Initialize the TestClient with the GitHub router
client = TestClient(router)

@pytest.fixture(scope="module")
def github_webhook_secret():
    """A dummy secret for testing GitHub webhook signatures."""
    return "supersecret_github_webhook_key"

@pytest.fixture(autouse=True)
def set_test_env_vars(github_webhook_secret):
    """Set environment variables for testing, and restore them after tests."""
    original_github_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    original_tenant_id = os.environ.get("KEEP_GITHUB_DEFAULT_TENANT_ID")

    os.environ["GITHUB_WEBHOOK_SECRET"] = github_webhook_secret
    os.environ["KEEP_GITHUB_DEFAULT_TENANT_ID"] = "test_tenant"

    yield

    if original_github_secret is not None:
        os.environ["GITHUB_WEBHOOK_SECRET"] = original_github_secret
    else:
        os.environ.pop("GITHUB_WEBHOOK_SECRET", None)

    if original_tenant_id is not None:
        os.environ["KEEP_GITHUB_DEFAULT_TENANT_ID"] = original_tenant_id
    else:
        os.environ.pop("KEEP_GITHUB_DEFAULT_TENANT_ID", None)


@pytest.fixture
def mock_alert_client():
    """Mocks the AlertClient and its post_alert method."""
    with patch("keep.api.alerts.integrations.github.AlertClient") as mock_client_cls:
        mock_instance = mock_client_cls.return_value
        yield mock_instance

@pytest.fixture
def mock_context_manager():
    """Mocks the global context_manager instance."""
    with patch("keep.api.alerts.integrations.github.context_manager") as mock_cm:
        # Mock its logger attribute
        mock_cm.logger = MagicMock()
        yield mock_cm

# --- Test verify_signature function ---

def generate_signature(payload: bytes, secret: str) -> str:
    """Helper to generate a valid GitHub signature."""
    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    return f"sha256={mac.hexdigest()}"

def test_verify_signature_valid(github_webhook_secret):
    payload = b'{"key": "value"}'
    signature = generate_signature(payload, github_webhook_secret)
    assert verify_signature(payload, signature, github_webhook_secret) is True

def test_verify_signature_invalid(github_webhook_secret):
    payload = b'{"key": "value"}'
    invalid_signature = "sha256=invalidhash"
    assert verify_signature(payload, invalid_signature, github_webhook_secret) is False

def test_verify_signature_missing_header(github_webhook_secret, mock_context_manager):
    payload = b'{"key": "value"}'
    assert verify_signature(payload, None, github_webhook_secret) is False
    mock_context_manager.logger.warning.assert_called_once_with("Missing signature header or secret for GitHub webhook verification.")

def test_verify_signature_missing_secret(mock_context_manager):
    payload = b'{"key": "value"}'
    signature = "sha256=somehash"
    assert verify_signature(payload, signature, "") is False
    mock_context_manager.logger.warning.assert_called_once_with("Missing signature header or secret for GitHub webhook verification.")


def test_verify_signature_unsupported_algorithm(github_webhook_secret, mock_context_manager):
    payload = b'{"key": "value"}'
    signature = "sha1=invalid"
    assert verify_signature(payload, signature, github_webhook_secret) is False
    mock_context_manager.logger.error.assert_called_once_with("Invalid signature algorithm: sha1")

def test_verify_signature_malformed_header(github_webhook_secret, mock_context_manager):
    payload = b'{"key": "value"}'
    signature = "sha256invalid" # Missing '='
    assert verify_signature(payload, signature, github_webhook_secret) is False
    mock_context_manager.logger.error.assert_called_once_with(f"Malformed signature header: {signature}")


# --- Test _github_event_to_alert function ---

@pytest.mark.parametrize(
    "event_type, payload, expected_name_substring, expected_status, expected_severity, expected_fingerprint_substring",
    [
        # Issues
        ("issues", {"action": "opened", "issue": {"title": "Bug found", "html_url": "url", "number": 1}, "repository": {"full_name": "org/repo"}, "sender": {"login": "user"}}, "Bug found (opened)", AlertStatus.FIRING, AlertSeverity.WARNING, "org/repo-issue-1"),
        ("issues", {"action": "closed", "issue": {"title": "Bug found", "html_url": "url", "number": 1}, "repository": {"full_name": "org/repo"}, "sender": {"login": "user"}}, "Bug found (closed)", AlertStatus.RESOLVED, AlertSeverity.INFO, "org/repo-issue-1"),
        ("issues", {"action": "opened", "issue": {"title": "Critical Bug", "html_url": "url", "number": 2, "severity": "critical"}, "repository": {"full_name": "org/repo"}, "sender": {"login": "user"}}, "Critical Bug (opened)", AlertStatus.FIRING, AlertSeverity.CRITICAL, "org/repo-issue-2"),
        # Pull Request
        ("pull_request", {"action": "opened", "pull_request": {"title": "New Feature", "html_url": "url", "number": 10, "merged": False}, "repository": {"full_name": "org/repo"}, "sender": {"login": "user"}}, "New Feature (opened)", AlertStatus.FIRING, AlertSeverity.INFO, "org/repo-pr-10"),
        ("pull_request", {"action": "closed", "pull_request": {"title": "New Feature", "html_url": "url", "number": 10, "merged": True}, "repository": {"full_name": "org/repo"}, "sender": {"login": "user"}}, "New Feature (closed)", AlertStatus.RESOLVED, AlertSeverity.INFO, "org/repo-pr-10"),
        ("pull_request", {"action": "closed", "pull_request": {"title": "Abandoned PR", "html_url": "url", "number": 11, "merged": False}, "repository": {"full_name": "org/repo"}, "sender": {"login": "user"}}, "Abandoned PR (closed)", AlertStatus.RESOLVED, AlertSeverity.INFO, "org/repo-pr-11"),
        # Push
        ("push", {"ref": "refs/heads/main", "after": "abc", "commits": [{},{}], "pusher": {"name": "testuser"}, "repository": {"full_name": "org/repo"}}, "Push to main in org/repo", AlertStatus.INFO, AlertSeverity.INFO, "org/repo-push-abc"),
        # Workflow Run
        ("workflow_run", {"action": "completed", "workflow_run": {"id": 123, "name": "Build", "status": "completed", "conclusion": "failure", "html_url": "url"}, "repository": {"full_name": "org/repo"}}, "Workflow Run: Build (completed)", AlertStatus.FIRING, AlertSeverity.ERROR, "org/repo-workflow-123"),
        ("workflow_run", {"action": "completed", "workflow_run": {"id": 124, "name": "Deploy", "status": "completed", "conclusion": "success", "html_url": "url"}, "repository": {"full_name": "org/repo"}}, "Workflow Run: Deploy (completed)", AlertStatus.RESOLVED, AlertSeverity.INFO, "org/repo-workflow-124"),
        ("workflow_run", {"action": "in_progress", "workflow_run": {"id": 125, "name": "Test", "status": "in_progress", "html_url": "url"}, "repository": {"full_name": "org/repo"}}, "Workflow Run: Test (in_progress)", AlertStatus.PENDING, AlertSeverity.INFO, "org/repo-workflow-125"),
        # Repository Vulnerability Alert
        ("repository_vulnerability_alert", {"action": "create", "alert": {"id": 1, "affected_package_name": "npm/react", "severity": "high"}, "repository": {"full_name": "org/repo"}}, "Vulnerability Alert: npm/react (create)", AlertStatus.FIRING, AlertSeverity.HIGH, "org/repo-vuln-alert-1"),
        ("repository_vulnerability_alert", {"action": "resolve", "alert": {"id": 1, "affected_package_name": "npm/react", "severity": "high"}, "repository": {"full_name": "org/repo"}}, "Vulnerability Alert: npm/react (resolve)", AlertStatus.RESOLVED, AlertSeverity.HIGH, "org/repo-vuln-alert-1"),
        # Security Advisory
        ("security_advisory", {"action": "published", "security_advisory": {"ghsa_id": "GHSA-123", "summary": "Critical Vulnerability", "severity": "critical"}, "repository": {"full_name": "org/repo"}}, "Security Advisory: Critical Vulnerability (published)", AlertStatus.FIRING, AlertSeverity.CRITICAL, "org/repo-sec-advisory-GHSA-123"),
        ("security_advisory", {"action": "withdrawn", "security_advisory": {"ghsa_id": "GHSA-123", "summary": "Critical Vulnerability", "severity": "critical"}, "repository": {"full_name": "org/repo"}}, "Security Advisory: Critical Vulnerability (withdrawn)", AlertStatus.RESOLVED, AlertSeverity.INFO, "org/repo-sec-advisory-GHSA-123"),
        # Dependabot Alert
        ("dependabot_alert", {"action": "create", "alert": {"number": 1, "state": "open", "dependency": {"package": {"name": "lodash"}}, "security_advisory": {"severity": "moderate"}}, "repository": {"full_name": "org/repo"}}, "Dependabot Alert: lodash (create)", AlertStatus.FIRING, AlertSeverity.WARNING, "org/repo-dependabot-alert-1"),
        ("dependabot_alert", {"action": "dismissed", "alert": {"number": 1, "state": "dismissed", "dependency": {"package": {"name": "lodash"}}, "security_advisory": {"severity": "moderate"}}, "repository": {"full_name": "org/repo"}}, "Dependabot Alert: lodash (dismissed)", AlertStatus.RESOLVED, AlertSeverity.WARNING, "org/repo-dependabot-alert-1"),
    ]
)
def test_github_event_to_alert(event_type, payload, expected_name_substring, expected_status, expected_severity, expected_fingerprint_substring):
    alert_dto = _github_event_to_alert(event_type, payload)

    assert alert_dto is not None
    assert expected_name_substring in alert_dto.name
    assert alert_dto.status == expected_status
    assert alert_dto.severity == expected_severity
    assert alert_dto.source == "github"
    assert DEFAULT_GITHUB_TENANT_ID == "test_tenant" # Ensure fixture tenant id is used
    assert expected_fingerprint_substring in alert_dto.id
    assert alert_dto.context == payload # Full payload should be in context

def test_github_event_to_alert_unhandled_event_type(mock_context_manager):
    event_type = "unhandled_event"
    payload = {"foo": "bar"}
    alert_dto = _github_event_to_alert(event_type, payload)
    assert alert_dto is None
    mock_context_manager.logger.debug.assert_called_once_with(f"Received unhandled GitHub event type: {event_type}")

def test_github_event_to_alert_fallback_fingerprint(mock_context_manager):
    event_type = "some_new_event" # Event type not explicitly handled in matches
    payload = {"test_key": "test_value"}
    alert_dto = _github_event_to_alert(event_type, payload)
    assert alert_dto is not None
    assert alert_dto.id.startswith(f"github-{event_type}-")
    # Verify fallback fingerprint contains a hash of the payload
    assert len(alert_dto.id) > len(f"github-{event_type}-")


# --- Test github_webhook endpoint ---

@patch("keep.api.alerts.integrations.github.AlertClient")
@patch("keep.api.alerts.integrations.github.verify_signature")
@patch("keep.api.alerts.integrations.github._github_event_to_alert")
def test_github_webhook_success(mock_event_to_alert, mock_verify_signature, MockAlertClient, github_webhook_secret, mock_context_manager):
    mock_verify_signature.return_value = True
    mock_alert_dto = AlertDto(
        id="test-id", name="Test Alert", status=AlertStatus.FIRING,
        severity=AlertSeverity.INFO, source="github", tenant_id="test_tenant"
    )
    mock_event_to_alert.return_value = mock_alert_dto
    mock_alert_client_instance = MockAlertClient.return_value

    test_payload = {"action": "opened", "issue": {"title": "Test Issue"}}
    test_event = "issues"
    
    response = client.post(
        "/github",
        headers={
            "X-GitHub-Event": test_event,
            "X-Hub-Signature-256": generate_signature(json.dumps(test_payload).encode(), github_webhook_secret)
        },
        json=test_payload,
    )

    assert response.status_code == 200
    assert "processed successfully" in response.text
    mock_verify_signature.assert_called_once()
    mock_event_to_alert.assert_called_once_with(test_event, test_payload)
    mock_alert_client_instance.post_alert.assert_called_once_with(mock_alert_dto)
    mock_context_manager.logger.info.assert_any_call(f"Posting GitHub alert: {mock_alert_dto.name}")


@patch("keep.api.alerts.integrations.github.verify_signature")
def test_github_webhook_invalid_signature(mock_verify_signature, mock_context_manager):
    mock_verify_signature.return_value = False
    test_payload = {"action": "opened"}
    response = client.post(
        "/github",
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=invalid"
        },
        json=test_payload,
    )
    assert response.status_code == 401
    assert "Invalid GitHub webhook signature" in response.json()["detail"]
    mock_context_manager.logger.error.assert_called_once_with("GitHub webhook signature verification failed.")


def test_github_webhook_missing_secret(mock_context_manager):
    os.environ.pop("GITHUB_WEBHOOK_SECRET") # Temporarily remove for this test
    test_payload = {"action": "opened"}
    response = client.post(
        "/github",
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=valid" # Signature doesn't matter here, secret is checked first
        },
        json=test_payload,
    )
    assert response.status_code == 500
    assert "Webhook secret not configured on Keep server" in response.json()["detail"]
    mock_context_manager.logger.error.assert_called_once_with("GITHUB_WEBHOOK_SECRET is not set in environment.")


def test_github_webhook_missing_event_header(mock_context_manager):
    test_payload = {"action": "opened"}
    response = client.post(
        "/github",
        headers={
            "X-Hub-Signature-256": generate_signature(json.dumps(test_payload).encode(), os.environ["GITHUB_WEBHOOK_SECRET"])
        },
        json=test_payload,
    )
    assert response.status_code == 400
    assert "Missing X-GitHub-Event header" in response.json()["detail"]
    mock_context_manager.logger.warning.assert_called_once_with("Missing X-GitHub-Event header.")

def test_github_webhook_empty_payload(mock_context_manager):
    response = client.post(
        "/github",
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": generate_signature(b'', os.environ["GITHUB_WEBHOOK_SECRET"])
        },
        content="", # Send empty body
    )
    assert response.status_code == 202
    assert "Empty payload received" in response.text
    mock_context_manager.logger.warning.assert_called_once_with("Received empty payload from GitHub webhook.")


def test_github_webhook_invalid_json_payload(github_webhook_secret, mock_context_manager):
    invalid_json_payload = b'{"action": "opened"' # Malformed JSON
    response = client.post(
        "/github",
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": generate_signature(invalid_json_payload, github_webhook_secret)
        },
        content=invalid_json_payload,
    )
    assert response.status_code == 400
    assert "Invalid JSON payload" in response.json()["detail"]
    mock_context_manager.logger.error.assert_called_once_with("Failed to decode JSON payload from GitHub webhook.")


@patch("keep.api.alerts.integrations.github._github_event_to_alert")
@patch("keep.api.alerts.integrations.github.verify_signature", return_value=True)
def test_github_webhook_unhandled_event_type(mock_verify_signature, mock_event_to_alert, mock_context_manager):
    mock_event_to_alert.return_value = None # Simulate unhandled event
    
    test_payload = {"action": "something"}
    response = client.post(
        "/github",
        headers={
            "X-GitHub-Event": "unknown_event",
            "X-Hub-Signature-256": generate_signature(json.dumps(test_payload).encode(), os.environ["GITHUB_WEBHOOK_SECRET"])
        },
        json=test_payload,
    )
    
    assert response.status_code == 202
    assert "ignored or no alert generated" in response.text
    mock_context_manager.logger.info.assert_called_with("No alert generated for GitHub event type: unknown_event")