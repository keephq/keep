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
    HTTPDigest,
    OAuth2PasswordBearer,
)
from pusher import Pusher
from sqlmodel import Session

from keep.api.core.config import AuthenticationType
from keep.api.core.db import get_api_key, get_session, get_user_by_api_key
from keep.api.core.rbac import Admin as AdminRole
from keep.api.core.rbac import get_role_by_role_name

logger = logging.getLogger(__name__)

auth_header = APIKeyHeader(name="X-API-KEY", scheme_name="API Key", auto_error=False)
http_digest = HTTPDigest(
    auto_error=False
)  # hack for grafana, they don't support api key header
http_basic = HTTPBasic(auto_error=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Just a fake random tenant id
SINGLE_TENANT_UUID = "keep"
SINGLE_TENANT_EMAIL = "admin@keephq"


@dataclasses.dataclass
class AuthenticatedEntity:
    tenant_id: str
    email: str


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


def __extract_api_key(
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


def _verify_api_key(
    request: Request,
    scopes: list[str] = [],
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
    api_key = __extract_api_key(request, api_key, authorization)

    tenant_api_key = get_api_key(api_key)
    if not tenant_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # validate scopes
    role = get_role_by_role_name(tenant_api_key.role)
    if not role.has_scopes(scopes):
        raise HTTPException(
            status_code=403,
            detail=f"You don't have the required scopes to access this resource [required scoopes: {scopes}]",
        )
    request.state.tenant_id = tenant_api_key.tenant_id
    return AuthenticatedEntity(tenant_api_key.tenant_id, tenant_api_key.created_by)


# init once so the cache will actually work
auth_domain = os.environ.get("AUTH0_DOMAIN")
if auth_domain:
    jwks_uri = f"https://{auth_domain}/.well-known/jwks.json"
    jwks_client = jwt.PyJWKClient(jwks_uri, cache_keys=True)


def _verify_bearer_token(
    scopes: list[str] = [], token: str = Depends(oauth2_scheme)
) -> str:
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
            if not role.has_scopes(scopes):
                raise HTTPException(
                    status_code=403,
                    detail="You don't have the required permissions to access this resource",
                )
            return AuthenticatedEntity(tenant_id, email)
        # authorization error
        except HTTPException:
            raise
        except jwt.exceptions.DecodeError:
            logger.exception("Failed to decode token")
            raise HTTPException(status_code=401, detail="Token is not a valid JWT")
        except Exception as e:
            logger.exception("Failed to validate token")
            raise HTTPException(status_code=401, detail=str(e))


def get_user_email_single_tenant(request: Request) -> str:
    # if we don't want to use authentication, return the single tenant id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.NO_AUTH.value
    ):
        return SINGLE_TENANT_UUID

    return get_user_email(request)


def _verify_bearer_token_single_tenant(
    scopes: list[str] = [], token: str = Depends(oauth2_scheme)
) -> AuthenticatedEntity:
    # if we don't want to use authentication, return the single tenant id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.NO_AUTH.value
    ):
        return AuthenticatedEntity(SINGLE_TENANT_UUID, SINGLE_TENANT_EMAIL)

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
            "role", str(AdminRole)
        )  # default to admin for backwards compatibility
        role = get_role_by_role_name(role_name)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT token")
    # validate scopes
    if not role.has_scopes(scopes):
        raise HTTPException(
            status_code=403,
            detail="You don't have the required permissions to access this resource",
        )
    return AuthenticatedEntity(tenant_id, email)


def _verify_api_key_single_tenant(
    request: Request,
    scopes: list[str] = [],
    api_key: str = Security(auth_header),
    authorization: HTTPAuthorizationCredentials = Security(http_basic),
    session: Session = Depends(get_session),
) -> AuthenticatedEntity:
    # if we don't want to use authentication, return the single tenant id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.NO_AUTH.value
    ):
        return AuthenticatedEntity(
            tenant_id=SINGLE_TENANT_UUID, email=SINGLE_TENANT_EMAIL
        )

    api_key = __extract_api_key(request, api_key, authorization)

    tenant_api_key = get_api_key(api_key)
    if not tenant_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    role = get_role_by_role_name(tenant_api_key.role)
    # validate scopes
    if not role.has_scopes(scopes):
        raise HTTPException(
            status_code=403,
            detail=f"You don't have the required scopes to access this resource [required scoopes: {scopes}]",
        )
    request.state.tenant_id = tenant_api_key.tenant_id
    return AuthenticatedEntity(tenant_api_key.tenant_id, tenant_api_key.created_by)


def AuthVerifier(scopes: list[str] = []):
    # Determine the authentication type from the environment variable
    auth_type = os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)

    # Return the appropriate verifier based on the auth type
    if auth_type == AuthenticationType.SINGLE_TENANT.value:
        return AuthVerifierSingleTenant(scopes)
    else:
        return AuthVerifierMultiTenant(scopes)


class AuthVerifierMultiTenant:
    """Handles authentication and authorization for multi tenant mode"""

    def __init__(self, scopes: list[str] = []) -> None:
        self.scopes = scopes

    def __call__(
        self,
        request: Request,
        api_key: Optional[str] = Security(auth_header),
        authorization: Optional[HTTPAuthorizationCredentials] = Security(http_basic),
        token: Optional[str] = Depends(oauth2_scheme),
    ) -> AuthenticatedEntity:
        # Attempt to verify API Key first
        if api_key:
            try:
                return _verify_api_key(request, self.scopes, api_key, authorization)
            # specific exceptions
            except HTTPException:
                raise
            # generic exception
            except Exception:
                logger.exception("Failed to validate API Key")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )
        # If API Key is not present or not valid, attempt to verify the token
        if token:
            try:
                return _verify_bearer_token(self.scopes, token)
            # specific exceptions
            except HTTPException:
                raise
            except Exception:
                logger.exception("Failed to validate token")
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

    def __call__(
        self,
        request: Request,
        api_key: Optional[str] = Security(auth_header),
        authorization: Optional[HTTPAuthorizationCredentials] = Security(http_basic),
        token: Optional[str] = Depends(oauth2_scheme),
    ) -> str:
        # Attempt to verify API Key first
        if api_key:
            try:
                return _verify_api_key_single_tenant(
                    request, self.scopes, api_key, authorization
                )
            # authorization error
            except HTTPException:
                raise
            except Exception:
                logger.exception("Failed to validate API Key")
                raise HTTPException(
                    status_code=401, detail="Invalid authentication credentials"
                )
        # If API Key is not present or not valid, attempt to verify the token
        if token:
            try:
                return _verify_bearer_token_single_tenant(self.scopes, token)
            # authorization error
            except HTTPException:
                raise
            except Exception:
                logger.exception("Failed to validate token")
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
        port=int(os.environ.get("PUSHER_PORT"))
        if os.environ.get("PUSHER_PORT")
        else None,
        app_id=os.environ.get("PUSHER_APP_ID"),
        key=os.environ.get("PUSHER_APP_KEY"),
        secret=os.environ.get("PUSHER_APP_SECRET"),
        ssl=False if os.environ.get("PUSHER_USE_SSL", False) is False else True,
        cluster=os.environ.get("PUSHER_CLUSTER"),
    )
