import fnmatch
from typing import Optional

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from keep.api.core.config import config
from keep.api.core.db import (
    create_user,
    update_user_last_sign_in,
    update_user_role,
    user_exists,
)
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import get_role_by_role_name


class Oauth2proxyAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.oauth2_proxy_user_header = config(
            "KEEP_OAUTH2_PROXY_USER_HEADER", default="x-forwarded-email"
        )
        self.oauth2_proxy_role_header = config(
            "KEEP_OAUTH2_PROXY_ROLE_HEADER", default="x-forwarded-groups"
        )
        self.auto_create_user = config("KEEP_OAUTH2_PROXY_AUTO_CREATE_USER", default=True)

        # Helper: parse comma-separated groups (supports wildcards)
        def parse_role_env(var_name: str, mapped_role: str):
            raw_value = config(var_name, default="")
            if not raw_value:
                return []
            groups = [v.strip() for v in raw_value.split(",") if v.strip()]
            return [(pattern, mapped_role) for pattern in groups]

        # Collect mappings (pattern → role)
        self.role_patterns = []
        self.role_patterns += parse_role_env("KEEP_OAUTH2_PROXY_ADMIN_ROLE", "admin")
        self.role_patterns += parse_role_env("KEEP_OAUTH2_PROXY_NOC_ROLE", "noc")
        self.role_patterns += parse_role_env("KEEP_OAUTH2_PROXY_WEBHOOK_ROLE", "webhook")

        self.logger.info(f"Oauth2proxy Auth Verifier initialized with patterns: {self.role_patterns}")

    def _match_role_pattern(self, role_name: str) -> Optional[str]:
        """Check if given role_name matches any configured wildcard pattern."""
        for pattern, mapped_role in self.role_patterns:
            if fnmatch.fnmatch(role_name, pattern):
                self.logger.debug(f"Matched role '{role_name}' to pattern '{pattern}' → {mapped_role}")
                return mapped_role
        return None

    def authenticate(
        self,
        request: Request,
        api_key: str,
        authorization: Optional[HTTPAuthorizationCredentials],
        token: Optional[str],
        *args,
        **kwargs,
    ) -> AuthenticatedEntity:
        # API key authentication first
        if api_key or request.headers.get("Authorization"):
            try:
                api_key = self._extract_api_key(request, api_key, authorization)
                if api_key:
                    self.logger.info("Attempting to authenticate with API key")
                    return self._verify_api_key(request, api_key, authorization)
            except Exception:
                pass  # fallback to header-based authentication

        # Header-based auth (via oauth2-proxy)
        user_name = request.headers.get(self.oauth2_proxy_user_header)
        if not user_name:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no user in {self.oauth2_proxy_user_header} header found",
            )

        role_header = request.headers.get(self.oauth2_proxy_role_header)
        if not role_header:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no role in {self.oauth2_proxy_role_header} header found",
            )

        # Multiple roles allowed in header
        roles = [r.strip() for r in role_header.split(",") if r.strip()]
        self.logger.debug(f"User {user_name} has roles from header: {roles}")

        # Define priority order
        role_priority = ["admin", "noc", "webhook"]
        mapped_role = None

        # Try to match according to priority
        for priority_role in role_priority:
            for role in roles:
                matched_role = self._match_role_pattern(role)
                if matched_role == priority_role:
                    try:
                        mapped_role = get_role_by_role_name(priority_role)
                        break
                    except HTTPException:
                        continue
            if mapped_role:
                break

        if not mapped_role:
            raise HTTPException(
                status_code=403,
                detail=f"No valid role found among {roles}",
            )

        # Auto-create or update user
        if self.auto_create_user and not user_exists(
            tenant_id=SINGLE_TENANT_UUID, username=user_name
        ):
            self.logger.info(f"Auto provisioning user: {user_name}")
            create_user(
                tenant_id=SINGLE_TENANT_UUID,
                username=user_name,
                role=mapped_role.get_name(),
                password="",
            )
        else:
            try:
                update_user_last_sign_in(tenant_id=SINGLE_TENANT_UUID, username=user_name)
                update_user_role(
                    tenant_id=SINGLE_TENANT_UUID,
                    username=user_name,
                    role=mapped_role.get_name(),
                )
            except Exception as e:
                self.logger.warning(f"Failed updating user data: {e}")

        self.logger.info(f"User {user_name} authenticated with role {mapped_role.get_name()}")
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=user_name,
            role=mapped_role.get_name(),
        )
