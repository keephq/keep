from typing import Optional

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from keep.api.core.db import create_user, user_exists
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase


class Oauth2proxyAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def authenticate(
        self,
        request: Request,
        api_key: str,
        authorization: Optional[HTTPAuthorizationCredentials],
    ) -> AuthenticatedEntity:

        # https://github.com/keephq/keep/issues/1203
        # get user name
        user_name = request.headers.get(self.impersonation_user_header)

        if not user_name:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no user in {self.impersonation_user_header} header found",
            )

        role = request.headers.get(self.impersonation_role_header)
        if not role:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no role in {self.impersonation_role_header} header found",
            )

        # auto provision user
        if self.impersonation_auto_create_user and not user_exists(user_name):
            self.logger.info(f"Auto provisioning user: {user_name}")
            create_user(
                tenant_id=SINGLE_TENANT_UUID, username=user_name, role=role, password=""
            )
            self.logger.info(f"User {user_name} created")

        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=user_name,
            role=role,
        )
