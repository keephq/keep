import os

import jwt
from fastapi import HTTPException

from keep.api.core.db import create_user, user_exists
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import Admin as AdminRole
from keep.identitymanager.rbac import get_role_by_role_name


class DbAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def _verify_bearer_token(self, token: str) -> AuthenticatedEntity:
        # validate the token
        jwt_secret = os.environ.get("KEEP_JWT_SECRET", "jwtsecret")
        # if default
        if jwt_secret == "jwtsecret":
            self.logger.warning(
                "KEEP_JWT_SECRET environment variable is not set, using default value. Should be set in production."
            )

        try:
            payload = jwt.decode(
                token,
                jwt_secret,
                algorithms="HS256",
            )
            tenant_id = payload.get("tenant_id")
            email = payload.get("email")
            role_name = payload.get(
                "role", AdminRole.get_name()
            )  # default to admin for backwards compatibility
            role = get_role_by_role_name(role_name)
        except Exception:
            self.logger.exception("Failed to decode JWT token")
            raise HTTPException(status_code=401, detail="Invalid JWT token")
        # validate scopes
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail="You don't have the required permissions to access this resource",
            )
        return AuthenticatedEntity(tenant_id, email, None, role_name)

    # create user for auto-provisioning
    def _provision_user(self, tenant_id, user_name, role):
        if not user_exists(tenant_id, user_name):
            create_user(tenant_id=tenant_id, username=user_name, role=role, password="")
