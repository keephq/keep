import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBasic,
    OAuth2PasswordBearer,
)

from keep.api.core.config import config
from keep.api.core.db import get_api_key, update_key_last_used
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.rbac import Admin as AdminRole
from keep.identitymanager.rbac import get_role_by_role_name

auth_header = APIKeyHeader(name="X-API-KEY", scheme_name="API Key", auto_error=False)
http_basic = HTTPBasic(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

ALL_RESOURCES = set()


def get_all_scopes() -> list[str]:
    """
    Get all scopes

    Returns:
        list: The list of scopes.
    """
    # read, write, delete and update for every resource:
    scopes = []
    for resource in ALL_RESOURCES:
        for action in ["read", "write", "delete", "update"]:
            scopes.append(f"{action}:{resource}")
    return scopes


class AuthVerifierBase:
    """
    Base class for authentication and authorization verification.

    This class provides a framework for implementing authentication and authorization
    in FastAPI applications. It supports multiple authentication methods including
    API keys, HTTP Basic Auth, and OAuth2 bearer tokens.

    Subclasses can override the following methods to customize the authentication
    and authorization process:
    - _verify_bearer_token: Implement token-based authentication
    - _verify_api_key: Customize API key verification
    - _authorize: Implement custom authorization logic

    The main entry point is the __call__ method, which handles the entire
    authentication and authorization flow.

    Attributes:
        scopes (list[str]): A list of required scopes for authorization.
        logger (logging.Logger): Logger for this class.

    """

    def __init__(self, scopes: list[str] = []) -> None:
        ALL_RESOURCES.update([scope.split(":")[1] for scope in scopes])
        self.scopes = scopes
        self.logger = logging.getLogger(__name__)
        self.impersonation_enabled = (
            config("KEEP_IMPERSONATION_ENABLED", default="false") == "true"
        )
        self.impersonation_user_header = config(
            "KEEP_IMPERSONATION_USER_HEADER", default="X-KEEP-USER"
        )
        self.impersonation_role_header = config(
            "KEEP_IMPERSONATION_ROLE_HEADER", default="X-KEEP-ROLE"
        )
        self.impersonation_auto_provision = (
            config("KEEP_IMPERSONATION_AUTO_PROVISION", default="false") == "true"
        )

    def __call__(
        self,
        request: Request,
        api_key: Optional[str] = Security(auth_header),
        authorization: Optional[HTTPAuthorizationCredentials] = Security(http_basic),
        token: Optional[str] = Depends(oauth2_scheme),
    ) -> AuthenticatedEntity:
        """
        Main entry point for authentication and authorization.

        Args:
            request (Request): The incoming request.
            api_key (Optional[str]): The API key from the header.
            authorization (Optional[HTTPAuthorizationCredentials]): The HTTP basic auth credentials.
            token (Optional[str]): The OAuth2 token.

        Returns:
            AuthenticatedEntity: The authenticated entity.

        Raises:
            HTTPException: If authentication or authorization fails.
        """
        self.logger.debug("Starting authentication process")
        authenticated_entity = self.authenticate(request, api_key, authorization, token)
        self.logger.debug(
            f"Authentication successful for entity: {authenticated_entity}"
        )

        self.logger.debug("Starting authorization process")
        self.authorize(authenticated_entity)
        self.logger.debug("Authorization successful")

        return authenticated_entity

    def authenticate(
        self,
        request: Request,
        api_key: Optional[str],
        authorization: Optional[HTTPAuthorizationCredentials],
        token: Optional[str],
    ) -> AuthenticatedEntity:
        """
        Authenticate the request using either token, API key, or HTTP basic auth.

        Args:
            request (Request): The incoming request.
            api_key (Optional[str]): The API key from the header.
            authorization (Optional[HTTPAuthorizationCredentials]): The HTTP basic auth credentials.
            token (Optional[str]): The OAuth2 token.

        Returns:
            AuthenticatedEntity: The authenticated entity.

        Raises:
            HTTPException: If authentication fails.
        """
        self.logger.debug("Attempting authentication")
        if token:
            self.logger.debug("Attempting to authenticate with bearer token")
            try:
                return self._verify_bearer_token(token)
            except HTTPException:
                raise
            except Exception:
                self.logger.exception("Failed to validate token")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )

        api_key = self._extract_api_key(request, api_key, authorization)
        if api_key:
            self.logger.debug("Attempting to authenticate with API key")
            try:
                return self._verify_api_key(request, api_key, authorization)
            except HTTPException:
                raise
            except Exception:
                self.logger.exception("Failed to validate API Key")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )
        self.logger.error("No valid authentication method found")
        raise HTTPException(
            status_code=401, detail="Missing authentication credentials"
        )

    def authorize(self, authenticated_entity: AuthenticatedEntity) -> None:
        """
        Authorize the authenticated entity.

        Args:
            authenticated_entity (AuthenticatedEntity): The authenticated entity to authorize.

        Raises:
            HTTPException: If authorization fails.
        """
        self.logger.debug(f"Authorizing entity: {authenticated_entity}")
        self._authorize(authenticated_entity)
        self.logger.debug("Authorization successful")

    def _authorize(self, authenticated_entity: AuthenticatedEntity) -> None:
        """
        Internal method to perform authorization.

        Args:
            authenticated_entity (AuthenticatedEntity): The authenticated entity to authorize.

        Raises:
            HTTPException: If the entity doesn't have the required scopes.
        """
        role = get_role_by_role_name(authenticated_entity.role)
        self.logger.debug(f"Checking scopes for role: {role}")
        if not role.has_scopes(self.scopes):
            self.logger.warning(f"Authorization failed. Required scopes: {self.scopes}")
            raise HTTPException(
                status_code=403,
                detail=f"You don't have the required scopes to access this resource [required scopes: {self.scopes}]",
            )
        self.logger.debug("Authorization successful")

    def _extract_api_key(
        self,
        request: Request,
        api_key: str,
        authorization: HTTPAuthorizationCredentials,
    ) -> str:
        """
        Extract the API key from various sources in the request.

        Args:
            request (Request): The incoming request.
            api_key (str): The API key from the header.
            authorization (HTTPAuthorizationCredentials): The HTTP basic auth credentials.

        Returns:
            str: The extracted API key.

        Raises:
            HTTPException: If no valid API key is found.
        """
        self.logger.debug("Extracting API key")
        api_key = api_key or request.query_params.get("api_key", None)
        if not api_key:
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
                self.logger.error("Failed to parse Authorization header")
                raise HTTPException(status_code=401, detail="Missing API Key")
            if scheme.lower() == "basic":
                api_key = authorization.password
            elif scheme.lower() == "digest":
                if not credentials:
                    self.logger.error("Invalid Digest credentials")
                    raise HTTPException(
                        status_code=403, detail="Invalid Digest credentials"
                    )
                else:
                    api_key = credentials
            else:
                self.logger.error(f"Unsupported authentication scheme: {scheme}")
                raise HTTPException(status_code=401, detail="Missing API Key")
        self.logger.debug("API key extracted successfully")
        return api_key

    def _verify_api_key(
        self,
        request: Request,
        api_key: str = Security(auth_header),
        authorization: HTTPAuthorizationCredentials = Security(http_basic),
    ) -> AuthenticatedEntity:
        """
        Verify the API key and return an authenticated entity.

        Args:
            request (Request): The incoming request.
            api_key (str): The API key to verify.
            authorization (HTTPAuthorizationCredentials): The HTTP basic auth credentials.

        Returns:
            AuthenticatedEntity: The authenticated entity.

        Raises:
            HTTPException: If the API key is invalid.
        """
        self.logger.debug("Verifying API key")
        tenant_api_key = get_api_key(api_key)
        if not tenant_api_key:
            self.logger.warning("Invalid API Key")
            raise HTTPException(status_code=401, detail="Invalid API Key")

        try:
            self.logger.debug("Updating API Key last used")
            update_key_last_used(
                tenant_api_key.tenant_id, reference_id=tenant_api_key.reference_id
            )
            self.logger.debug("Successfully updated API Key last used")
        except Exception:
            self.logger.exception("Failed to update API Key last used")

        request.state.tenant_id = tenant_api_key.tenant_id
        self.logger.debug(f"API key verified for tenant: {tenant_api_key.tenant_id}")
        # check if impersonation is enabled, if not, return the api key's authenticated entity
        if not self.impersonation_enabled:
            return AuthenticatedEntity(
                tenant_api_key.tenant_id,
                tenant_api_key.created_by,
                tenant_api_key.reference_id,
                tenant_api_key.role,
            )
        # check if impersonation headers are present
        user_name = request.headers.get(self.impersonation_user_header)
        role = request.headers.get(self.impersonation_role_header)
        # if not, return the apikey's authenticated entity
        if not user_name or not role:
            return AuthenticatedEntity(
                tenant_api_key.tenant_id,
                tenant_api_key.created_by,
                tenant_api_key.reference_id,
                tenant_api_key.role,
            )

        self.logger.info("Impersonating user")
        user_name = request.headers.get(self.impersonation_user_header)
        role = request.headers.get(self.impersonation_role_header)
        if not user_name or not role:
            raise HTTPException(status_code=401, detail="Impersonation headers missing")

        # TODO - validate authorization meaning api key X has access to impersonate user Y
        #        for now, only admin users can impersonate
        if tenant_api_key.role != AdminRole.get_name():
            self.logger.error("Impersonation not allowed for non-admin users")
            raise HTTPException(
                status_code=401, detail="Impersonation not allowed for non-admin users"
            )

        # auto provision user
        if self.impersonation_auto_provision:
            self.logger.info(f"Auto provisioning user: {user_name}")
            self._provision_user(tenant_api_key.tenant_id, user_name, role)
            self.logger.info(f"User {user_name} provisioned successfully")

        self.logger.info("User impersonated successfully")
        return AuthenticatedEntity(
            tenant_id=tenant_api_key.tenant_id,
            email=user_name,
            api_key_name=None,
            role=role,
        )

    def _provision_user(self, tenant_api_key, user_name, role):
        """
        Create a user for impersonation.

        Args:
            tenant_api_key: The API key used for impersonation.
            user_name: The name of the user to create.
            role: The role of the user to create.
        """
        raise NotImplementedError(
            "User provisioning not implemented"
            " for {}".format(self.__class__.__name__)
        )

    def _verify_bearer_token(self, token: str) -> AuthenticatedEntity:
        """
        Verify the bearer token and return an authenticated entity.

        Args:
            token (str): The bearer token to verify.

        Returns:
            AuthenticatedEntity: The authenticated entity.

        Raises:
            NotImplementedError: This method needs to be implemented in subclasses.
        """
        self.logger.error("_verify_bearer_token() method not implemented")
        raise NotImplementedError(
            "_verify_bearer_token() method not implemented"
            " for {}".format(self.__class__.__name__)
        )
