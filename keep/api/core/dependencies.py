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
from sqlmodel import Session

from keep.api.core.config import AuthenticationType
from keep.api.core.db import (
    get_api_key,
    get_session,
    get_user_by_api_key,
    update_key_last_used,
)
from keep.api.core.rbac import Admin as AdminRole
from keep.api.core.rbac import get_role_by_role_name

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


def get_user_email(request: Request) -> str | None:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("get_user_email"):
        token = request.headers.get("Authorization")
        if token:
            token = token.split(" ")[1]
            decoded_token = jwt.decode(token, options={"verify_signature": False})
            return decoded_token.get("email")
        elif "x-api-key" in request.headers:
            username = get_user_by_api_key(request.headers["x-api-key"])
            return username
        else:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )


def extract_api_key(
    request: Request, api_key: str, authorization: HTTPAuthorizationCredentials
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


# init once so the cache will actually work
auth_domain = os.environ.get("AUTH0_DOMAIN")
if auth_domain:
    jwks_uri = f"https://{auth_domain}/.well-known/jwks.json"
    jwks_client = jwt.PyJWKClient(
        jwks_uri, cache_keys=True, headers={"User-Agent": "keep-api"}
    )
else:
    jwks_client = None


def AuthVerifier(scopes: list[str] = []):
    # Determine the authentication type from the environment variable
    auth_type = os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)

    # Return the appropriate verifier based on the auth type
    if auth_type == AuthenticationType.MULTI_TENANT.value:
        return AuthVerifierMultiTenant(scopes)
    else:
        return AuthVerifierSingleTenant(scopes)


class AuthVerifierMultiTenant:
    """Handles authentication and authorization for multi tenant mode"""

    def __init__(self, scopes: list[str] = []) -> None:
        self.scopes = scopes

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        # Took the implementation from here:
        #   https://github.com/auth0-developer-hub/api_fastapi_python_hello-world/blob/main/application/json_web_token.py
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("verify_bearer_token"):
            if not token:
                raise HTTPException(status_code=401, detail="No token provided 👈")
            try:
                auth_audience = os.environ.get("AUTH0_AUDIENCE")
                issuer = f"https://{auth_domain}/"
                jwt_signing_key = jwks_client.get_signing_key_from_jwt(token).key
                payload = jwt.decode(
                    token,
                    jwt_signing_key,
                    algorithms="RS256",
                    audience=auth_audience,
                    issuer=issuer,
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

    def _verify_api_key(
        self,
        request: Request,
        api_key: str = Security(auth_header),
        authorization: HTTPAuthorizationCredentials = Security(http_basic),
    ) -> AuthenticatedEntity:
        """
        Verifies that a customer is allowed to access the API.

        Args:
            api_key (str, optional): The API key extracted from X-API-KEY header. Defaults to Security(auth_header).

        Raises:
            HTTPException: 401 if the user is unauthorized.

        Returns:
            str: The tenant id.
        """
        tenant_api_key = get_api_key(api_key)
        if not tenant_api_key:
            raise HTTPException(status_code=401, detail="Invalid API Key")
        # update last used
        else:
            logger.debug("Updating API Key last used")
            try:
                update_key_last_used(
                    tenant_api_key.tenant_id, reference_id=tenant_api_key.reference_id
                )
            except Exception:
                logger.exception("Failed to update API Key last used")
                pass
            logger.debug("Successfully updated API Key last used")

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
        api_key = extract_api_key(request, api_key, authorization)
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


class AuthVerifierSingleTenant:
    """Handles authentication and authorization for single tenant mode"""

    def __init__(self, scopes: list[str] = []) -> None:
        self.scopes = scopes

    def _verify_api_key(
        self,
        request: Request,
        api_key: str = Security(auth_header),
        authorization: HTTPAuthorizationCredentials = Security(http_basic),
        session: Session = Depends(get_session),
    ) -> AuthenticatedEntity:
        # if we don't want to use authentication, return the single tenant id
        tenant_api_key = get_api_key(api_key)

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
        else:
            logger.debug("Updating API Key last used")
            try:
                update_key_last_used(
                    tenant_api_key.tenant_id, reference_id=tenant_api_key.reference_id
                )
            except Exception:
                logger.exception("Failed to update API Key last used")
                pass
            logger.debug("Successfully updated API Key last used")

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
            tenant_id = payload.get("keep_tenant_id")
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
            # authorization error
            except HTTPException:
                raise
            except Exception:
                logger.exception("Failed to validate token")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )
        # Attempt to verify API Key first
        api_key = extract_api_key(request, api_key, authorization)
        if api_key:
            try:
                return self._verify_api_key(request, api_key, authorization)
            # authorization error
            except HTTPException:
                raise
            except Exception:
                logger.exception("Failed to validate API Key")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )
        raise HTTPException(
            status_code=401, detail="Missing authentication credentials"
        )


def get_pusher_client() -> Pusher | None:
    if os.environ.get("PUSHER_DISABLED", "false") == "true":
        return None

    # TODO: defaults on open source no docker
    return Pusher(
        host=os.environ.get("PUSHER_HOST"),
        port=(
            int(os.environ.get("PUSHER_PORT"))
            if os.environ.get("PUSHER_PORT")
            else None
        ),
        app_id=os.environ.get("PUSHER_APP_ID"),
        key=os.environ.get("PUSHER_APP_KEY"),
        secret=os.environ.get("PUSHER_APP_SECRET"),
        ssl=False if os.environ.get("PUSHER_USE_SSL", False) is False else True,
        cluster=os.environ.get("PUSHER_CLUSTER"),
    )
