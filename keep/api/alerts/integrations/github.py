import hmac
import hashlib
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, Request, HTTPException, Header, Response
from pydantic import ValidationError

# Assuming these imports are available in the Keep project structure
from keep.contextmanager.contextmanager import ContextManager
from keep.alerts.base.alert import AlertDto, AlertStatus, AlertSeverity
from keep.client.alert_client import AlertClient # Actual AlertClient
from keep.api.core.config import config

# Initialize FastAPI router for GitHub webhooks
router = APIRouter()

# Get the default tenant_id for GitHub alerts from environment or configuration
# This is a fallback/default and can be overridden if a more complex multi-tenant
# mapping is implemented (e.g., based on GitHub repo or organization).
DEFAULT_GITHUB_TENANT_ID = os.environ.get("KEEP_GITHUB_DEFAULT_TENANT_ID") or \
                           config.get("KEEP_GITHUB_DEFAULT_TENANT_ID", "default")

# The ContextManager is initialized once globally. For testing, it needs to be mocked.
# In a production Keep setup, ContextManager handles logging, telemetry, etc.
# If DEFAULT_GITHUB_TENANT_ID is critical for ContextManager, it should be validated earlier in app lifecycle.
# For now, we proceed assuming it's correctly set or Keep's startup handles a missing value.
try:
    context_manager = ContextManager(tenant_id=DEFAULT_GITHUB_TENANT_ID)
except Exception as e:
    # Log and re-raise or handle this gracefully if ContextManager initialization fails
    print(f"ERROR: Failed to initialize ContextManager for GitHub integration: {e}")
    # Depending on Keep's architecture, this might need a more robust startup check.
    # For a bounty solution, we assume the environment is set for the app to run.
    raise

def get_alert_client():
    """
    Returns an instance of the AlertClient for the default tenant.
    This function exists to allow easier mocking in tests.
    """
    return AlertClient(tenant_id=DEFAULT_GITHUB_TENANT_ID)

def verify_signature(payload: bytes, signature_header: Optional[str], secret: str) -> bool:
    """
    Verify the GitHub webhook signature.

    Args:
        payload (bytes): The raw payload of the webhook request.
        signature_header (Optional[str]): The value of the 'X-Hub-Signature-256' header.
        secret (str): The webhook secret configured in GitHub and Keep.

    Returns:
        bool: True if the signature is valid, False otherwise.
    """
    if not signature_header or not secret:
        context_manager.logger.warning("Missing signature header or secret for GitHub webhook verification.")
        return False

    try:
        sha_name, signature = signature_header.split("=", 1)
        if sha_name != "sha256":
            context_manager.logger.error(f"Invalid signature algorithm: {sha_name}")
            return False
    except ValueError:
        context_manager.logger.error(f"Malformed signature header: {signature_header}")
        return False

    mac = hmac.new(secret.encode("utf-8"), msg=payload, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

def _github_event_to_alert(event_type: str, payload: Dict[str, Any]) -> Optional[AlertDto]:
    """
    Converts a GitHub webhook event payload into a Keep AlertDto.

    Args:
        event_type (str): The type of GitHub event (from X-GitHub-Event header).
        payload (Dict[str, Any]): The parsed JSON payload of the webhook.

    Returns:
        Optional[AlertDto]: A Keep AlertDto object, or None if the event is not relevant or unhandled.
    """
    alert_name = f"GitHub {event_type} event"
    status = AlertStatus.FIRING
    severity = AlertSeverity.INFO
    description = f"Unhandled GitHub {event_type} event."
    source_url = None
    fingerprint = None
    # Use current UTC time for lastReceived and pushed
    current_time = datetime.now(timezone.utc).isoformat()
    last_received = current_time
    pushed = current_time

    repo_full_name = payload.get("repository", {}).get("full_name", "unknown/repository")
    repo_url = payload.get("repository", {}).get("html_url")
    sender_login = payload.get("sender", {}).get("login", "GitHub")

    match event_type:
        case "issues":
            issue = payload.get("issue", {})
            action = payload.get("action")
            issue_title = issue.get("title", "No Title")
            issue_url = issue.get("html_url")
            issue_number = issue.get("number")
            alert_name = f"GitHub Issue: {issue_title} ({action})"
            source_url = issue_url
            fingerprint = f"{repo_full_name}-issue-{issue_number}"
            description = f"Issue '{issue_title}' ({issue_number}) in {repo_full_name} was {action} by {sender_login}."

            match action:
                case "opened" | "reopened":
                    status = AlertStatus.FIRING
                    severity = AlertSeverity.WARNING
                case "closed":
                    status = AlertStatus.RESOLVED
                    severity = AlertSeverity.INFO
                case _: # For other actions like assigned, labeled, deleted, etc.
                    status = AlertStatus.FIRING
                    severity = AlertSeverity.INFO
            
            # Allow for custom severity fields if present (e.g., from custom workflows)
            if issue.get("severity"):
                match issue["severity"].lower():
                    case "critical": severity = AlertSeverity.CRITICAL
                    case "high": severity = AlertSeverity.HIGH
                    case "moderate": severity = AlertSeverity.WARNING
                    case "low": severity = AlertSeverity.INFO
                    case _: pass # Keep previous severity if not a recognized custom severity


        case "pull_request":
            pr = payload.get("pull_request", {})
            action = payload.get("action")
            pr_title = pr.get("title", "No Title")
            pr_url = pr.get("html_url")
            pr_number = pr.get("number")
            alert_name = f"GitHub Pull Request: {pr_title} ({action})"
            source_url = pr_url
            fingerprint = f"{repo_full_name}-pr-{pr_number}"
            description = f"Pull request '{pr_title}' ({pr_number}) in {repo_full_name} was {action} by {sender_login}."

            match action:
                case "opened" | "reopened":
                    status = AlertStatus.FIRING
                    severity = AlertSeverity.INFO
                case "closed":
                    # If merged, it's definitively resolved. Otherwise, it might be just closed without merge.
                    if pr.get("merged"):
                        status = AlertStatus.RESOLVED
                        description += " (merged)."
                    else:
                        status = AlertStatus.RESOLVED # Closed without merge
                    severity = AlertSeverity.INFO
                case _:
                    status = AlertStatus.FIRING
                    severity = AlertSeverity.INFO

        case "push":
            ref = payload.get("ref", "").split("/")[-1]
            commits_count = len(payload.get("commits", []))
            pusher_name = payload.get("pusher", {}).get("name", sender_login)
            compare_url = payload.get("compare")
            alert_name = f"GitHub Push to {ref} in {repo_full_name}"
            source_url = compare_url or repo_url
            fingerprint = f"{repo_full_name}-push-{payload.get('after')}"
            description = f"{pusher_name} pushed {commits_count} commit(s) to branch '{ref}' in {repo_full_name}."
            status = AlertStatus.INFO
            severity = AlertSeverity.INFO

        case "workflow_run":
            workflow_run = payload.get("workflow_run", {})
            action = payload.get("action")
            workflow_name = workflow_run.get("name", "Unknown Workflow")
            status_workflow = workflow_run.get("status")
            conclusion = workflow_run.get("conclusion")
            run_url = workflow_run.get("html_url")
            alert_name = f"GitHub Workflow Run: {workflow_name} ({action})"
            source_url = run_url
            fingerprint = f"{repo_full_name}-workflow-{workflow_run.get('id')}"
            description = f"Workflow '{workflow_name}' in {repo_full_name} was {action}."
            if conclusion:
                description += f" Conclusion: {conclusion}."

            if conclusion == "failure":
                status = AlertStatus.FIRING
                severity = AlertSeverity.ERROR
            elif conclusion == "success":
                status = AlertStatus.RESOLVED
                severity = AlertSeverity.INFO
            elif status_workflow == "queued" or status_workflow == "in_progress":
                status = AlertStatus.PENDING
                severity = AlertSeverity.INFO
            else:
                status = AlertStatus.INFO # Default for other actions like requested, in_progress, etc.
                severity = AlertSeverity.INFO

        case "repository_vulnerability_alert":
            alert = payload.get("alert", {})
            action = payload.get("action")
            dependency_name = alert.get("affected_package_name", "unknown dependency")
            severity_str = alert.get("severity", "unknown")
            alert_url = alert.get("external_reference")
            alert_name = f"GitHub Vulnerability Alert: {dependency_name} ({action})"
            source_url = alert_url or repo_url
            fingerprint = f"{repo_full_name}-vuln-alert-{alert.get('id')}"
            description = f"Vulnerability alert for '{dependency_name}' in {repo_full_name} was {action}. Severity: {severity_str.upper()}."

            match action:
                case "create":
                    status = AlertStatus.FIRING
                case "resolve":
                    status = AlertStatus.RESOLVED
                case _: # For dismiss, revert, etc.
                    status = AlertStatus.FIRING

            match severity_str.lower():
                case "critical": severity = AlertSeverity.CRITICAL
                case "high": severity = AlertSeverity.HIGH
                case "moderate": severity = AlertSeverity.WARNING
                case "low": severity = AlertSeverity.INFO
                case _: severity = AlertSeverity.INFO

        case "security_advisory":
            advisory = payload.get("security_advisory", {})
            action = payload.get("action")
            advisory_summary = advisory.get("summary", "No summary")
            advisory_id = advisory.get("ghsa_id", advisory.get("id", "unknown_id"))
            advisory_url = advisory.get("html_url")
            alert_name = f"GitHub Security Advisory: {advisory_summary} ({action})"
            source_url = advisory_url or repo_url
            fingerprint = f"{repo_full_name}-sec-advisory-{advisory_id}"
            description = f"Security Advisory '{advisory_summary}' for {repo_full_name} was {action}."

            match action:
                case "published":
                    status = AlertStatus.FIRING
                    # Security advisories are generally critical by default
                    severity = AlertSeverity.CRITICAL
                case "withdrawn":
                    status = AlertStatus.RESOLVED
                    severity = AlertSeverity.INFO
                case _:
                    status = AlertStatus.FIRING
                    severity = AlertSeverity.CRITICAL

            # Refine severity based on advisory.severity if available and granular enough
            advisory_severity = advisory.get("severity", "unknown")
            match advisory_severity.lower():
                case "critical": severity = AlertSeverity.CRITICAL
                case "high": severity = AlertSeverity.HIGH
                case "moderate": severity = AlertSeverity.WARNING
                case "low": severity = AlertSeverity.INFO
                case _: pass # Keep default or previously set

        case "dependabot_alert":
            alert = payload.get("alert", {})
            action = payload.get("action")
            package_name = alert.get("dependency", {}).get("package", {}).get("name", "unknown package")
            alert_state = alert.get("state") # open, fixed, dismissed, auto_dismissed
            alert_url = alert.get("html_url")
            alert_name = f"GitHub Dependabot Alert: {package_name} ({action})"
            source_url = alert_url or repo_url
            fingerprint = f"{repo_full_name}-dependabot-alert-{alert.get('number')}"
            description = f"Dependabot alert for '{package_name}' in {repo_full_name} was {action}. State: {alert_state}."

            match alert_state:
                case "open":
                    status = AlertStatus.FIRING
                case "fixed" | "dismissed" | "auto_dismissed":
                    status = AlertStatus.RESOLVED
                case _:
                    status = AlertStatus.FIRING

            # Dependabot alerts usually have a severity field within security_advisory
            alert_severity = alert.get("security_advisory", {}).get("severity", "unknown")
            match alert_severity.lower():
                case "critical": severity = AlertSeverity.CRITICAL
                case "high": severity = AlertSeverity.HIGH
                case "moderate": severity = AlertSeverity.WARNING
                case "low": severity = AlertSeverity.INFO
                case _: severity = AlertSeverity.INFO

        case _:
            context_manager.logger.debug(f"Received unhandled GitHub event type: {event_type}")
            return None # Ignore unhandled events, or create a generic alert if desired

    if not fingerprint:
        # Fallback fingerprint generation if not set by event type handler
        fingerprint = f"github-{event_type}-{hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]}"

    return AlertDto(
        id=fingerprint,
        name=alert_name,
        status=status,
        severity=severity,
        source="github",
        url=source_url or repo_url,
        pushed=pushed,
        lastReceived=last_received,
        description=description,
        context=payload, # Store the full payload in context
        tenant_id=DEFAULT_GITHUB_TENANT_ID,
    )

@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """
    Receives GitHub webhook events, verifies their signature, and processes them into Keep alerts.
    """
    try:
        # Get raw payload bytes for signature verification
        payload_bytes = await request.body()
        
        # Retrieve the secret from environment variables or configuration
        webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
        if not webhook_secret:
            context_manager.logger.error("GITHUB_WEBHOOK_SECRET is not set in environment.")
            raise HTTPException(
                status_code=500, detail="Webhook secret not configured on Keep server."
            )

        # Verify signature
        if not verify_signature(payload_bytes, x_hub_signature_256, webhook_secret):
            context_manager.logger.error("GitHub webhook signature verification failed.")
            raise HTTPException(
                status_code=401, detail="Invalid GitHub webhook signature."
            )

        if not x_github_event:
            context_manager.logger.warning("Missing X-GitHub-Event header.")
            raise HTTPException(status_code=400, detail="Missing X-GitHub-Event header.")

        if not payload_bytes:
            context_manager.logger.warning("Received empty payload from GitHub webhook.")
            return Response(status_code=202, content="Empty payload received.")

        payload = json.loads(payload_bytes)
        context_manager.logger.debug(f"Received GitHub webhook, event type: {x_github_event}")

        alert_dto = _github_event_to_alert(x_github_event, payload)

        if alert_dto:
            context_manager.logger.info(f"Posting GitHub alert: {alert_dto.name}")
            alert_client = get_alert_client()
            alert_client.post_alert(alert_dto)
            return Response(status_code=200, content=f"Alert '{alert_dto.name}' processed successfully.")
        else:
            context_manager.logger.info(f"No alert generated for GitHub event type: {x_github_event}")
            return Response(status_code=202, content=f"Event type '{x_github_event}' ignored or no alert generated.")

    except json.JSONDecodeError:
        context_manager.logger.error("Failed to decode JSON payload from GitHub webhook.")
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")
    except ValidationError as e:
        context_manager.logger.error(f"Failed to validate AlertDto: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid alert data: {e}")
    except Exception as e:
        context_manager.logger.exception("An unexpected error occurred during GitHub webhook processing.")
        raise HTTPException(status_code=500, detail=f"Internal server error: {e}")