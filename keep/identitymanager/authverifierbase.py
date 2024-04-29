import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBasic,
    OAuth2PasswordBearer,
)

from keep.api.core.db import get_api_key, update_key_last_used
from keep.api.core.rbac import get_role_by_role_name
from keep.identitymanager.authenticatedentity import AuthenticatedEntity

auth_header = APIKeyHeader(name="X-API-KEY", scheme_name="API Key", auto_error=False)
http_basic = HTTPBasic(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


class AuthVerifierBase:
    def __init__(self, scopes: list[str] = []) -> None:
        self.scopes = scopes
        self.logger = logging.getLogger(__name__)

    def __call__(
        self,
        request: Request,
        api_key: Optional[str] = Security(auth_header),
        authorization: Optional[HTTPAuthorizationCredentials] = Security(http_basic),
        token: Optional[str] = Depends(oauth2_scheme),
    ) -> AuthenticatedEntity:
        # Attempt to verify the token first
        if token:
            try:
                return self._verify_bearer_token(token)
            # specific exceptions
            except HTTPException:
                raise
            except Exception:
                self.logger.exception("Failed to validate token")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )

        # Attempt to verify API Key
        api_key = self._extract_api_key(request, api_key, authorization)
        if api_key:
            try:
                return self._verify_api_key(request, api_key, authorization)
            # specific exceptions
            except HTTPException:
                raise
            # generic exception
            except Exception:
                self.logger.exception("Failed to validate API Key")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )
        raise HTTPException(
            status_code=401, detail="Missing authentication credentials"
        )

    def _extract_api_key(
        self,
        request: Request,
        api_key: str,
        authorization: HTTPAuthorizationCredentials,
    ) -> str:
        """
        Extracts the API key from the request.
        API key can be passed in the following ways:
        1. X-API-KEY header
        2. api_key query param
        3. Basic auth header
        4. Digest auth header

        Args:
            request (Request): FastAPI request object
            api_key (str): The API key extracted from X-API-KEY header
            authorization (HTTPAuthorizationCredentials): The credentials extracted from the Authorization header

        Raises:
            HTTPException: 401 if the user is unauthorized.

        Returns:
            str: api key
        """
        api_key = api_key or request.query_params.get("api_key", None)
        if not api_key:
            # if its from Amazon SNS and we don't have any bearer - force basic auth
            if (
                not authorization
                and "Amazon Simple Notification Service Agent"
                in request.headers.get("user-agent")
            ):
                self.logger.warning("Got an SNS request without any auth")
                raise HTTPException(
                    status_code=401,
                    headers={"WWW-Authenticate": "Basic"},
                    detail="Missing API Key",
                )

            auth_header = request.headers.get("Authorization")
            try:
                scheme, _, credentials = auth_header.partition(" ")
            except Exception:
                raise HTTPException(status_code=401, detail="Missing API Key")
            # support basic auth (e.g. AWS SNS)
            if scheme.lower() == "basic":
                api_key = authorization.password
            # support Digest auth (e.g. Grafana)
            elif scheme.lower() == "digest":
                # Validate Digest credentials
                if not credentials:
                    raise HTTPException(
                        status_code=403, detail="Invalid Digest credentials"
                    )
                else:
                    api_key = credentials
            else:
                raise HTTPException(status_code=401, detail="Missing API Key")
        return api_key

    def _verify_api_key(
        self,
        request: Request,
        api_key: str = Security(auth_header),
        authorization: HTTPAuthorizationCredentials = Security(http_basic),
    ) -> AuthenticatedEntity:
        # generic implementation for API_KEY authentication
        tenant_api_key = get_api_key(api_key)
        if not tenant_api_key:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        # update last used
        else:
            self.logger.debug("Updating API Key last used")
            try:
                update_key_last_used(
                    tenant_api_key.tenant_id, reference_id=tenant_api_key.reference_id
                )
            except Exception:
                self.logger.exception("Failed to update API Key last used")
                pass
            self.logger.debug("Successfully updated API Key last used")

        # validate scopes
        role = get_role_by_role_name(tenant_api_key.role)
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail=f"You don't have the required scopes to access this resource [required scopes: {self.scopes}]",
            )
        request.state.tenant_id = tenant_api_key.tenant_id

        return AuthenticatedEntity(
            tenant_api_key.tenant_id,
            tenant_api_key.created_by,
            tenant_api_key.reference_id,
        )

    def _verify_bearer_token(self, token: str) -> AuthenticatedEntity:
        raise NotImplementedError(
            "_verify_bearer_token() method not implemented"
            " for {}".format(self.__class__.__name__)
        )
