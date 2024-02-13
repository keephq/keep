import dataclasses
import logging
import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBasic,
    OAuth2PasswordBearer,
)
from pusher import Pusher

from keep.api.core.config import AuthenticationType
from keep.api.core.db import get_api_key
from keep.api.core.rbac import Admin as AdminRole
from keep.api.core.rbac import get_role_by_role_name
from keycloak import KeycloakOpenID

logger = logging.getLogger(__name__)

auth_header = APIKeyHeader(name="X-API-KEY", scheme_name="API Key", auto_error=False)
http_basic = HTTPBasic(auto_error=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Just a fake random tenant id
SINGLE_TENANT_UUID = "keep"
SINGLE_TENANT_EMAIL = "admin@keephq"


@dataclasses.dataclass
class AuthenticatedEntity:
    tenant_id: str
    email: str
    api_key_name: Optional[str] = None
    role: Optional[str] = None


def AuthVerifier(scopes: list[str] = []):
    # Took the implementation from here:
    #   https://github.com/auth0-developer-hub/api_fastapi_python_hello-world/blob/main/application/json_web_token.py

    # Basically it's a factory function that returns the appropriate verifier based on the auth type

    # Determine the authentication type from the environment variable
    auth_type = os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
    # Return the appropriate verifier based on the auth type
    if auth_type == AuthenticationType.MULTI_TENANT.value:
        return AuthVerifierMultiTenant(scopes)
    elif auth_type == AuthenticationType.KEYCLOAK.value:
        return AuthVerifierKeycloak(scopes)
    else:
        return AuthVerifierSingleTenant(scopes)


class AuthVerifierBase:
    def __init__(self, scopes: list[str] = []) -> None:
        self.scopes = scopes

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
                logger.exception("Failed to validate token")
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
                logger.exception("Failed to validate API Key")
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
                logger.warning("Got an SNS request without any auth")
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
        # if its no_auth mode, return the single tenant id
        if (
            os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
            == AuthenticationType.NO_AUTH.value
        ):
            return AuthenticatedEntity(
                tenant_id=SINGLE_TENANT_UUID,
                email=SINGLE_TENANT_EMAIL,
                api_key_name="single_tenant_api_key",  # just a placeholder
                role=AdminRole.get_name(),
            )

        if not tenant_api_key:
            raise HTTPException(status_code=401, detail="Invalid API Key")

        role = get_role_by_role_name(tenant_api_key.role)
        # validate scopes
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

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        raise NotImplementedError("You must implement this method")


class AuthVerifierMultiTenant(AuthVerifierBase):
    """Handles authentication and authorization for multi tenant mode"""

    def __init__(self, scopes: list[str] = []) -> None:
        # TODO: this verifier should be instansiate once and not for every endpoint/route
        #       to better cache the jwks keys
        super().__init__(scopes)
        # init once so the cache will actually work
        self.auth_domain = os.environ.get("AUTH0_DOMAIN")
        if not self.auth_domain:
            raise Exception("Missing AUTH0_DOMAIN environment variable")
        self.jwks_uri = f"https://{self.auth_domain}/.well-known/jwks.json"
        # Note: cache_keys is set to True to avoid fetching the jwks keys on every request
        #       but it currently caches only per-route. After moving this auth verifier to be a singleton, we can cache it globally
        self.jwks_client = jwt.PyJWKClient(self.jwks_uri, cache_keys=True)
        self.issuer = f"https://{self.auth_domain}/"
        self.auth_audience = os.environ.get("AUTH0_AUDIENCE")

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("verify_bearer_token"):
            if not token:
                raise HTTPException(status_code=401, detail="No token provided 👈")
            try:
                jwt_signing_key = self.jwks_client.get_signing_key_from_jwt(token).key
                payload = jwt.decode(
                    token,
                    jwt_signing_key,
                    algorithms="RS256",
                    audience=self.auth_audience,
                    issuer=self.issuer,
                    leeway=60,
                )
                tenant_id = payload.get("keep_tenant_id")
                role_name = payload.get(
                    "keep_role", AdminRole.get_name()
                )  # default to admin for backwards compatibility
                email = payload.get("email")
                role = get_role_by_role_name(role_name)
                # validate scopes
                if not role.has_scopes(self.scopes):
                    raise HTTPException(
                        status_code=403,
                        detail="You don't have the required permissions to access this resource",
                    )
                return AuthenticatedEntity(tenant_id, email, role=role_name)
            # authorization error
            except HTTPException:
                raise
            except jwt.exceptions.DecodeError:
                logger.exception("Failed to decode token")
                raise HTTPException(status_code=401, detail="Token is not a valid JWT")
            except Exception as e:
                logger.exception("Failed to validate token")
                raise HTTPException(status_code=401, detail=str(e))


class AuthVerifierSingleTenant(AuthVerifierBase):
    """Handles authentication and authorization for single tenant mode"""

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        # if we don't want to use authentication, return the single tenant id
        if (
            os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
            == AuthenticationType.NO_AUTH.value
        ):
            return AuthenticatedEntity(
                tenant_id=SINGLE_TENANT_UUID,
                email=SINGLE_TENANT_EMAIL,
                api_key_name=None,
                role=AdminRole.get_name(),
            )

        # else, validate the token
        jwt_secret = os.environ.get("KEEP_JWT_SECRET")
        if not jwt_secret:
            raise HTTPException(status_code=401, detail="Missing JWT secret")

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
            raise HTTPException(status_code=401, detail="Invalid JWT token")
        # validate scopes
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail="You don't have the required permissions to access this resource",
            )
        return AuthenticatedEntity(tenant_id, email, None, role_name)


class AuthVerifierKeycloak(AuthVerifierBase):
    """Handles authentication and authorization for Keycloak"""

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        self.keycloak_url = os.environ.get("KEYCLOAK_URL")
        self.keycloak_realm = os.environ.get("KEYCLOAK_REALM")
        self.keycloak_client_id = os.environ.get("KEYCLOAK_CLIENT_ID")
        self.keycloak_audience = os.environ.get("KEYCLOAK_AUDIENCE")
        if (
            not self.keycloak_url
            or not self.keycloak_realm
            or not self.keycloak_client_id
        ):
            raise Exception(
                "Missing KEYCLOAK_URL, KEYCLOAK_REALM or KEYCLOAK_CLIENT_ID environment variable"
            )

        self.keycloak_client = KeycloakOpenID(
            server_url=self.keycloak_url,
            realm_name=self.keycloak_realm,
            client_id=self.keycloak_client_id,
        )
        self.keycloak_public_key = (
            "-----BEGIN PUBLIC KEY-----\n"
            + self.keycloak_client.public_key()
            + "\n-----END PUBLIC KEY-----"
        )
        self.verify_options = {
            "verify_signature": True,
            "verify_aud": True,
            "verify_exp": True,
        }

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        # verify keycloak token
        try:
            payload = self.keycloak_client.decode_token(
                token, key=self.keycloak_public_key, options=self.verify_options
            )
            tenant_id = payload.get("keep_tenant_id")
            email = payload.get("preferred_username")
            role_name = payload.get("keep_role")
            if not role_name:
                raise HTTPException(
                    status_code=401, detail="Invalid Keycloak token - no role in token"
                )
            role = get_role_by_role_name(role_name)
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid Keycloak token")

        # validate scopes
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail="You don't have the required permissions to access this resource",
            )
        return AuthenticatedEntity(tenant_id, email, None, role_name)


def get_pusher_client() -> Pusher | None:
    if os.environ.get("PUSHER_DISABLED", "false") == "true":
        return None

    # TODO: defaults on open source no docker
    return Pusher(
        host=os.environ.get("PUSHER_HOST"),
        port=int(os.environ.get("PUSHER_PORT"))
        if os.environ.get("PUSHER_PORT")
        else None,
        app_id=os.environ.get("PUSHER_APP_ID"),
        key=os.environ.get("PUSHER_APP_KEY"),
        secret=os.environ.get("PUSHER_APP_SECRET"),
        ssl=False if os.environ.get("PUSHER_USE_SSL", False) is False else True,
        cluster=os.environ.get("PUSHER_CLUSTER"),
    )
