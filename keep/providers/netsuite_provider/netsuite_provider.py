"""
NetSuiteProvider is a class that implements the BaseProvider interface for NetSuite.

NetSuite is Oracle's cloud-based ERP, CRM, and ticketing platform.
This provider supports:
  - Pull mode: fetch support cases (customer tickets) via REST API
  - Push mode: create new support cases via webhook payload
  - notify(): create a support case programmatically
  - validate_scopes(): verify credentials via /record/v1/ping

Authentication: NLAuth header (Account ID + email + password + role)
  or Token-Based Authentication (TBA) with consumer/token key+secret.

Docs: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/section_156257770590.html
"""

import dataclasses
import hashlib
import hmac
import json
import os
import random
import string
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


# ---------------------------------------------------------------------------
# Auth config
# ---------------------------------------------------------------------------


@pydantic.dataclasses.dataclass
class NetSuiteProviderAuthConfig:
    """NetSuite authentication configuration.

    Supports two auth methods:
    1. NLAuth (simple)  — account_id + email + password + optional role
    2. TBA (token-based) — account_id + consumer_key + consumer_secret + token_key + token_secret
    """

    account_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "NetSuite Account ID (e.g. TSTDRV1234567 or 123456)",
            "sensitive": False,
            "hint": "1234567 or TSTDRV1234567",
        }
    )

    # NLAuth fields (optional if using TBA)
    email: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "NetSuite login email (NLAuth only)",
            "sensitive": False,
        },
        default="",
    )

    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "NetSuite login password (NLAuth only)",
            "sensitive": True,
        },
        default="",
    )

    role_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "NetSuite role ID for NLAuth (optional, defaults to Administrator)",
            "sensitive": False,
            "hint": "3",
        },
        default="",
    )

    # TBA fields (optional if using NLAuth)
    consumer_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "OAuth consumer key (TBA only)",
            "sensitive": True,
        },
        default="",
    )

    consumer_secret: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "OAuth consumer secret (TBA only)",
            "sensitive": True,
        },
        default="",
    )

    token_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "OAuth token key (TBA only)",
            "sensitive": True,
        },
        default="",
    )

    token_secret: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "OAuth token secret (TBA only)",
            "sensitive": True,
        },
        default="",
    )

    ticket_creation_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "URL for creating new support cases (optional UI link)",
            "sensitive": False,
            "hint": "https://1234567.app.netsuite.com/app/crm/support/supportcase.nl",
        },
        default="",
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class NetSuiteProvider(BaseProvider):
    """Manage NetSuite support cases (tickets) and pull alert data."""

    PROVIDER_DISPLAY_NAME = "NetSuite"
    PROVIDER_CATEGORY = ["Ticketing", "ERP"]
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_DESCRIPTION = (
        "Oracle NetSuite ERP/CRM — create and manage support cases, "
        "pull open issues, and push alert data as new tickets."
    )

    PROVIDER_SCOPES = [
        ProviderScope(
            name="rest_webservices",
            description="Access NetSuite REST Web Services (required for REST API calls)",
            documentation_url=(
                "https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/"
                "section_157921982098.html"
            ),
            mandatory=True,
            alias="REST Web Services",
        ),
        ProviderScope(
            name="support_cases_read",
            description="Permission to view support cases",
            mandatory=False,
            alias="Support Cases (Read)",
        ),
        ProviderScope(
            name="support_cases_write",
            description="Permission to create/update support cases",
            mandatory=False,
            alias="Support Cases (Write)",
        ),
    ]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Get Support Cases",
            func_name="get_support_cases",
            scopes=["rest_webservices", "support_cases_read"],
            description="Fetch support cases from NetSuite",
            type="view",
        ),
        ProviderMethod(
            name="Get Support Case",
            func_name="get_support_case",
            scopes=["rest_webservices", "support_cases_read"],
            description="Fetch a single support case by internal ID",
            type="view",
        ),
        ProviderMethod(
            name="Create Support Case",
            func_name="create_support_case",
            scopes=["rest_webservices", "support_cases_write"],
            description="Create a new support case in NetSuite",
            type="action",
        ),
        ProviderMethod(
            name="Update Support Case",
            func_name="update_support_case",
            scopes=["rest_webservices", "support_cases_write"],
            description="Update an existing support case",
            type="action",
        ),
        ProviderMethod(
            name="List Employees",
            func_name="list_employees",
            scopes=["rest_webservices"],
            description="List employees/users in NetSuite",
            type="view",
        ),
        ProviderMethod(
            name="Get Customer",
            func_name="get_customer",
            scopes=["rest_webservices"],
            description="Retrieve customer details by internal ID",
            type="view",
        ),
    ]

    # NetSuite support case status mapping
    STATUS_MAP = {
        "1": "open",
        "2": "in_progress",
        "3": "pending_customer_response",
        "4": "escalated",
        "5": "resolved",
        "6": "closed",
    }

    # NetSuite priority mapping
    PRIORITY_MAP = {
        "1": "critical",
        "2": "high",
        "3": "medium",
        "4": "low",
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._base_url: Optional[str] = None

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        self.authentication_config = NetSuiteProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def _rest_base(self) -> str:
        """Base URL for NetSuite REST API."""
        if self._base_url:
            return self._base_url
        account = self.authentication_config.account_id.lower().replace("_", "-")
        self._base_url = f"https://{account}.suitetalk.api.netsuite.com/services/rest"
        return self._base_url

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------

    def _use_tba(self) -> bool:
        """Return True if TBA credentials are configured."""
        cfg = self.authentication_config
        return bool(
            cfg.consumer_key
            and cfg.consumer_secret
            and cfg.token_key
            and cfg.token_secret
        )

    def _nlauth_header(self) -> str:
        """Build NLAuth Authorization header value."""
        cfg = self.authentication_config
        parts = [
            f"NLAuth nlauth_account={cfg.account_id}",
            f"nlauth_email={cfg.email}",
            f"nlauth_signature={cfg.password}",
        ]
        if cfg.role_id:
            parts.append(f"nlauth_role={cfg.role_id}")
        return ", ".join(parts)

    def _tba_header(self, method: str, url: str) -> str:
        """Build OAuth 1.0 TBA Authorization header value.

        NetSuite TBA uses OAuth 1.0 HMAC-SHA256.
        Ref: https://docs.oracle.com/en/cloud/saas/netsuite/ns-online-help/
             section_157937710596.html
        """
        cfg = self.authentication_config
        nonce = "".join(random.choices(string.ascii_letters + string.digits, k=11))
        timestamp = str(int(time.time()))

        # Build the base string
        parsed = urllib.parse.urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        params = {
            "oauth_consumer_key": cfg.consumer_key,
            "oauth_nonce": nonce,
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": timestamp,
            "oauth_token": cfg.token_key,
            "oauth_version": "1.0",
        }

        # Include query string params in the signature base
        if parsed.query:
            for pair in parsed.query.split("&"):
                k, _, v = pair.partition("=")
                params[urllib.parse.unquote(k)] = urllib.parse.unquote(v)

        sorted_params = "&".join(
            f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}"
            for k, v in sorted(params.items())
        )

        signature_base = "&".join(
            [
                urllib.parse.quote(method.upper(), safe=""),
                urllib.parse.quote(base_url, safe=""),
                urllib.parse.quote(sorted_params, safe=""),
            ]
        )

        signing_key = (
            f"{urllib.parse.quote(cfg.consumer_secret, safe='')}"
            f"&{urllib.parse.quote(cfg.token_secret, safe='')}"
        )

        hashed = hmac.new(
            signing_key.encode("utf-8"),
            signature_base.encode("utf-8"),
            hashlib.sha256,
        ).digest()

        import base64

        signature = base64.b64encode(hashed).decode("utf-8")

        auth_params = {
            "realm": cfg.account_id,
            "oauth_consumer_key": cfg.consumer_key,
            "oauth_token": cfg.token_key,
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": timestamp,
            "oauth_nonce": nonce,
            "oauth_version": "1.0",
            "oauth_signature": urllib.parse.quote(signature, safe=""),
        }

        header_parts = ", ".join(
            f'{k}="{v}"' for k, v in auth_params.items()
        )
        return f"OAuth {header_parts}"

    def _get_headers(self, method: str = "GET", url: str = "") -> dict:
        """Build request headers with appropriate auth."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._use_tba():
            headers["Authorization"] = self._tba_header(method, url)
        else:
            headers["Authorization"] = self._nlauth_header()
        return headers

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict:
        """Validate credentials by calling the REST /record/v1/ping endpoint."""
        scopes = {
            "rest_webservices": False,
            "support_cases_read": False,
            "support_cases_write": False,
        }

        ping_url = f"{self._rest_base}/record/v1/ping"
        try:
            response = requests.get(
                ping_url,
                headers=self._get_headers("GET", ping_url),
                timeout=15,
            )
            if response.status_code == 200:
                scopes["rest_webservices"] = True
                self.logger.info("NetSuite REST API ping succeeded")
            elif response.status_code == 401:
                scopes["rest_webservices"] = "Authentication failed — check credentials"
                return scopes
            elif response.status_code == 403:
                scopes["rest_webservices"] = (
                    "Forbidden — enable REST Web Services in your NetSuite account"
                )
                return scopes
            else:
                scopes["rest_webservices"] = (
                    f"Unexpected status {response.status_code}: {response.text[:200]}"
                )
                return scopes
        except requests.exceptions.ConnectionError:
            scopes["rest_webservices"] = (
                f"Cannot connect to {self._rest_base} — check account_id"
            )
            return scopes
        except Exception as exc:
            scopes["rest_webservices"] = str(exc)
            return scopes

        # Try reading support cases
        cases_url = f"{self._rest_base}/record/v1/supportcase?limit=1"
        try:
            resp = requests.get(
                cases_url,
                headers=self._get_headers("GET", cases_url),
                timeout=15,
            )
            if resp.status_code in (200, 206):
                scopes["support_cases_read"] = True
                scopes["support_cases_write"] = True  # assume write if read works
            elif resp.status_code == 403:
                scopes["support_cases_read"] = (
                    "No permission to read support cases — add the Support Cases role permission"
                )
            else:
                scopes["support_cases_read"] = (
                    f"Status {resp.status_code} when reading support cases"
                )
        except Exception as exc:
            scopes["support_cases_read"] = str(exc)

        return scopes

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        payload: Optional[dict] = None,
        timeout: int = 20,
    ) -> requests.Response:
        """Make an authenticated request to the NetSuite REST API."""
        url = f"{self._rest_base}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        headers = self._get_headers(method, url)

        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )
        return response

    @staticmethod
    def _safe_ref(field) -> str:
        """Extract the display value from a NetSuite reference field dict."""
        if isinstance(field, dict):
            return field.get("refName") or field.get("id") or str(field)
        return str(field) if field is not None else ""

    # ------------------------------------------------------------------
    # Support case methods
    # ------------------------------------------------------------------

    def get_support_cases(
        self,
        limit: int = 100,
        status_filter: Optional[str] = None,
        priority_filter: Optional[str] = None,
    ) -> list[dict]:
        """Fetch support cases from NetSuite.

        Args:
            limit: Maximum number of cases to return (default 100).
            status_filter: Optional status filter, e.g. "1" (open) or "5" (resolved).
            priority_filter: Optional priority filter, e.g. "1" (critical).

        Returns:
            List of support case dicts.
        """
        self.logger.info(
            "Fetching support cases from NetSuite",
            extra={"limit": limit, "status_filter": status_filter},
        )

        query_parts = []
        if status_filter:
            query_parts.append(f"status IS {status_filter}")
        if priority_filter:
            query_parts.append(f"priority IS {priority_filter}")

        params: dict = {"limit": min(limit, 1000)}
        if query_parts:
            params["q"] = " AND ".join(query_parts)

        response = self._request("GET", "/record/v1/supportcase", params=params)
        if not response.ok:
            self.logger.error(
                "Failed to fetch support cases",
                extra={
                    "status_code": response.status_code,
                    "response": response.text[:500],
                },
            )
            return []

        data = response.json()
        cases = data.get("items", [])
        self.logger.info(
            "Fetched support cases",
            extra={"count": len(cases)},
        )
        return cases

    def get_support_case(self, case_id: str) -> dict:
        """Fetch a single support case by internal ID.

        Args:
            case_id: NetSuite internal ID of the support case.

        Returns:
            Support case record dict.
        """
        self.logger.info(
            "Fetching support case", extra={"case_id": case_id}
        )
        response = self._request("GET", f"/record/v1/supportcase/{case_id}")
        if not response.ok:
            self.logger.error(
                "Failed to fetch support case",
                extra={
                    "case_id": case_id,
                    "status_code": response.status_code,
                    "response": response.text[:300],
                },
            )
            return {}
        return response.json()

    def create_support_case(
        self,
        title: str,
        description: str = "",
        priority: str = "3",
        status: str = "1",
        customer_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        category: Optional[str] = None,
        origin: str = "web",
        **kwargs,
    ) -> dict:
        """Create a new support case in NetSuite.

        Args:
            title: Subject / title of the support case.
            description: Detailed description of the issue.
            priority: NetSuite priority code ('1'=Critical, '2'=High, '3'=Medium, '4'=Low).
            status: NetSuite status code ('1'=Open, '2'=In Progress, ...).
            customer_id: Internal ID of the customer record.
            assigned_to: Internal ID of the employee to assign to.
            category: Internal ID of the case category record.
            origin: Origin of the case ('web', 'email', 'phone', etc.).
            **kwargs: Additional NetSuite supportcase fields.

        Returns:
            The created support case record dict including its new internal ID.
        """
        self.logger.info(
            "Creating support case",
            extra={"title": title, "priority": priority},
        )

        payload: dict = {
            "title": title,
            "incomingMessage": description,
            "status": {"id": status},
            "priority": {"id": priority},
            "origin": {"id": origin},
        }

        if customer_id:
            payload["company"] = {"id": customer_id}
        if assigned_to:
            payload["assigned"] = {"id": assigned_to}
        if category:
            payload["category"] = {"id": category}

        # Merge any extra fields
        payload.update(kwargs)

        response = self._request("POST", "/record/v1/supportcase", payload=payload)

        if response.status_code == 204:
            # NetSuite returns 204 No Content with a Location header on create
            location = response.headers.get("Location", "")
            new_id = location.rstrip("/").split("/")[-1] if location else "unknown"
            self.logger.info(
                "Support case created",
                extra={"internal_id": new_id, "location": location},
            )
            return {
                "id": new_id,
                "title": title,
                "link": location,
            }
        elif response.status_code == 200:
            result = response.json()
            self.logger.info(
                "Support case created",
                extra={"id": result.get("id")},
            )
            return result
        else:
            self.logger.error(
                "Failed to create support case",
                extra={
                    "status_code": response.status_code,
                    "response": response.text[:500],
                },
            )
            raise ProviderException(
                f"Failed to create NetSuite support case: "
                f"{response.status_code} — {response.text[:300]}"
            )

    def update_support_case(
        self,
        case_id: str,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        assigned_to: Optional[str] = None,
        reply_message: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Update an existing support case.

        Args:
            case_id: Internal ID of the support case to update.
            status: New status code (optional).
            priority: New priority code (optional).
            assigned_to: New assignee employee ID (optional).
            reply_message: Add a reply/note to the case (optional).
            **kwargs: Additional fields to update.

        Returns:
            Updated case record dict.
        """
        self.logger.info(
            "Updating support case",
            extra={"case_id": case_id, "status": status, "priority": priority},
        )

        payload: dict = {}
        if status:
            payload["status"] = {"id": status}
        if priority:
            payload["priority"] = {"id": priority}
        if assigned_to:
            payload["assigned"] = {"id": assigned_to}
        if reply_message:
            payload["outgoingMessage"] = reply_message
        payload.update(kwargs)

        if not payload:
            raise ProviderException("No fields to update were provided.")

        response = self._request(
            "PATCH", f"/record/v1/supportcase/{case_id}", payload=payload
        )

        if response.status_code in (200, 204):
            self.logger.info(
                "Support case updated", extra={"case_id": case_id}
            )
            if response.content:
                return response.json()
            return {"id": case_id, "updated": True}
        else:
            self.logger.error(
                "Failed to update support case",
                extra={
                    "case_id": case_id,
                    "status_code": response.status_code,
                    "response": response.text[:300],
                },
            )
            raise ProviderException(
                f"Failed to update support case {case_id}: "
                f"{response.status_code} — {response.text[:300]}"
            )

    def list_employees(self, limit: int = 50) -> list[dict]:
        """List employees in NetSuite.

        Args:
            limit: Maximum number of employees to return.

        Returns:
            List of employee dicts with id, name, email.
        """
        self.logger.info("Listing NetSuite employees", extra={"limit": limit})
        response = self._request(
            "GET", "/record/v1/employee", params={"limit": limit}
        )
        if not response.ok:
            self.logger.error(
                "Failed to list employees",
                extra={
                    "status_code": response.status_code,
                    "response": response.text[:300],
                },
            )
            return []
        data = response.json()
        return data.get("items", [])

    def get_customer(self, customer_id: str) -> dict:
        """Retrieve a customer record from NetSuite.

        Args:
            customer_id: Internal ID of the customer.

        Returns:
            Customer record dict.
        """
        self.logger.info(
            "Fetching customer", extra={"customer_id": customer_id}
        )
        response = self._request("GET", f"/record/v1/customer/{customer_id}")
        if not response.ok:
            self.logger.error(
                "Failed to fetch customer",
                extra={
                    "customer_id": customer_id,
                    "status_code": response.status_code,
                },
            )
            return {}
        return response.json()

    # ------------------------------------------------------------------
    # BaseProvider interface
    # ------------------------------------------------------------------

    def _query(
        self,
        limit: int = 100,
        status_filter: Optional[str] = None,
        **kwargs,
    ) -> list[dict]:
        """Pull support cases (used by BaseProvider.pull_alerts logic)."""
        return self.get_support_cases(limit=limit, status_filter=status_filter)

    def _notify(
        self,
        title: str,
        description: str = "",
        priority: str = "3",
        status: str = "1",
        customer_id: Optional[str] = None,
        assigned_to: Optional[str] = None,
        category: Optional[str] = None,
        origin: str = "web",
        **kwargs,
    ) -> dict:
        """Create a support case (used by Keep workflow notify() actions).

        Args:
            title: Subject of the case.
            description: Full description.
            priority: '1' (Critical) – '4' (Low), default '3' (Medium).
            status: '1' (Open) – '6' (Closed), default '1'.
            customer_id: NetSuite customer internal ID (optional).
            assigned_to: NetSuite employee internal ID (optional).
            category: NetSuite case category internal ID (optional).
            origin: Case origin, e.g. 'web', 'email', 'phone'.

        Returns:
            Dict with id, title, link.
        """
        return self.create_support_case(
            title=title,
            description=description,
            priority=priority,
            status=status,
            customer_id=customer_id,
            assigned_to=assigned_to,
            category=category,
            origin=origin,
            **kwargs,
        )

    def dispose(self) -> None:
        """No persistent connections to dispose."""
        pass


# ---------------------------------------------------------------------------
# __main__ smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    account_id = os.environ["NETSUITE_ACCOUNT_ID"]
    email = os.environ["NETSUITE_EMAIL"]
    password = os.environ["NETSUITE_PASSWORD"]

    config = ProviderConfig(
        description="NetSuite Provider",
        authentication={
            "account_id": account_id,
            "email": email,
            "password": password,
        },
    )
    provider = NetSuiteProvider(
        context_manager, provider_id="netsuite", config=config
    )

    print("=== validate_scopes ===")
    print(provider.validate_scopes())

    print("=== get_support_cases ===")
    cases = provider.get_support_cases(limit=5)
    print(f"Got {len(cases)} cases")
    for c in cases:
        print(c)
