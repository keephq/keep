import json
from typing import Optional

from fastapi import Request
from fastapi.security import HTTPAuthorizationCredentials

from keep.api.core.db import get_api_key
from keep.api.core.dependencies import SINGLE_TENANT_EMAIL, SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase
from keep.identitymanager.rbac import Admin as AdminRole


class NoAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def _verify_bearer_token(self, token: str) -> AuthenticatedEntity:
        try:
            token_payload = json.loads(token)
            tenant_id = token_payload["tenant_id"] or SINGLE_TENANT_UUID
            email = token_payload["user_id"] or SINGLE_TENANT_EMAIL
            return AuthenticatedEntity(
                tenant_id=tenant_id,
                email=email,
                role=AdminRole.get_name(),
            )
        except Exception:
            return AuthenticatedEntity(
                tenant_id=SINGLE_TENANT_UUID,
                email=SINGLE_TENANT_EMAIL,
                role=AdminRole.get_name(),
            )

    def _verify_api_key(
        self,
        request: Request,
        api_key: str,
        authorization: Optional[HTTPAuthorizationCredentials],
    ) -> AuthenticatedEntity:

        tenant_api_key = get_api_key(api_key)
        # this is ok, since we are in noauth mode
        if not tenant_api_key:
            return AuthenticatedEntity(
                tenant_id=SINGLE_TENANT_UUID,
                email=SINGLE_TENANT_EMAIL,
                role=AdminRole.get_name(),
            )

        # for e2e tests where multiple tenants are supported (per tenant api key)
        return AuthenticatedEntity(
            tenant_id=tenant_api_key.tenant_id,
            email=SINGLE_TENANT_EMAIL,
            role=AdminRole.get_name(),
        )
