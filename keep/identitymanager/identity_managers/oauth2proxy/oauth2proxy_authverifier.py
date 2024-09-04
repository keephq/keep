from typing import Optional

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

from keep.api.core.config import config
from keep.api.core.db import create_user, user_exists
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import get_role_by_role_name


class Oauth2proxyAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.oauth2_proxy_user_header = config(
            "KEEP_OAUTH2_PROXY_USER_HEADER", default="X-Auth-Request-Email"
        )
        self.oauth2_proxy_role_header = config(
            "KEEP_OAUTH2_PROXY_ROLE_HEADER", default="X-Auth-Request-Role"
        )
        self.auto_create_user = config(
            "KEEP_OAUTH2_PROXY_AUTO_CREATE_USER", default=True
        )
        self.logger.info("Oauth2proxy Auth Verifier initialized")

    def authenticate(
        self,
        request: Request,
        api_key: str,
        authorization: Optional[HTTPAuthorizationCredentials],
        token: Optional[str],
    ) -> AuthenticatedEntity:

        # https://github.com/keephq/keep/issues/1203
        # get user name
        self.logger.info(
            f"Authenticating user with {self.oauth2_proxy_user_header} header"
        )
        user_name = request.headers.get(self.oauth2_proxy_user_header)

        if not user_name:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no user in {self.oauth2_proxy_user_header} header found",
            )

        role = request.headers.get(self.oauth2_proxy_role_header)
        if not role:
            raise HTTPException(
                status_code=401,
                detail=f"Unauthorized - no role in {self.oauth2_proxy_role_header} header found",
            )

        # will raise exception if role not found
        get_role_by_role_name(role)

        # auto provision user
        if self.auto_create_user and not user_exists(user_name):
            self.logger.info(f"Auto provisioning user: {user_name}")
            create_user(
                tenant_id=SINGLE_TENANT_UUID, username=user_name, role=role, password=""
            )
            self.logger.info(f"User {user_name} created")

        self.logger.info(f"User {user_name} authenticated with role {role}")
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID,
            email=user_name,
            role=role,
        )
