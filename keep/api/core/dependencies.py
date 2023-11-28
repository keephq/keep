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
from keep.api.core.db import get_api_key, get_session

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


def get_user_email(request: Request) -> str | None:
    token = request.headers.get("Authorization")
    if token:
        token = token.split(" ")[1]
        decoded_token = jwt.decode(token, options={"verify_signature": False})
        return decoded_token.get("email")
    elif "x-api-key" in request.headers:
        return "apikey@keephq.dev"
    else:
        raise HTTPException(
            status_code=401, detail="Invalid authentication credentials"
        )


def verify_api_key(
    request: Request,
    api_key: str = Security(auth_header),
    authorization: HTTPAuthorizationCredentials = Security(http_basic),
) -> str:
    """
    Verifies that a customer is allowed to access the API.

    Args:
        api_key (str, optional): The API key extracted from X-API-KEY header. Defaults to Security(auth_header).

    Raises:
        HTTPException: 401 if the user is unauthorized.

    Returns:
        str: The tenant id.
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

    tenant_api_key = get_api_key(api_key)
    if not tenant_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    request.state.tenant_id = tenant_api_key.tenant_id
    return tenant_api_key.tenant_id


def verify_bearer_token(token: str = Depends(oauth2_scheme)) -> str:
    # Took the implementation from here:
    #   https://github.com/auth0-developer-hub/api_fastapi_python_hello-world/blob/main/application/json_web_token.py
    if not token:
        raise HTTPException(status_code=401, detail="No token provided 👈")
    try:
        auth_domain = os.environ.get("AUTH0_DOMAIN")
        auth_audience = os.environ.get("AUTH0_AUDIENCE")
        jwks_uri = f"https://{auth_domain}/.well-known/jwks.json"
        issuer = f"https://{auth_domain}/"
        jwks_client = jwt.PyJWKClient(jwks_uri)
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
        return tenant_id
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


def verify_bearer_token_single_tenant(token: str = Depends(oauth2_scheme)) -> str:
    # if we don't want to use authentication, return the single tenant id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.NO_AUTH.value
    ):
        return SINGLE_TENANT_UUID

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
        return tenant_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid JWT token")


def verify_api_key_single_tenant(
    request: Request,
    api_key: str = Security(auth_header),
    authorization: HTTPAuthorizationCredentials = Security(http_basic),
    session: Session = Depends(get_session),
) -> str:
    # if we don't want to use authentication, return the single tenant id
    if (
        os.environ.get("AUTH_TYPE", AuthenticationType.NO_AUTH.value)
        == AuthenticationType.NO_AUTH.value
    ):
        return SINGLE_TENANT_UUID

    tenant_api_key = get_api_key(api_key)
    if not tenant_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    request.state.tenant_id = tenant_api_key.tenant_id
    return tenant_api_key.tenant_id


def verify_token_or_key(
    request: Request,
    api_key: Optional[str] = Security(auth_header),
    authorization: Optional[HTTPAuthorizationCredentials] = Security(http_basic),
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    # Attempt to verify API Key first
    if api_key:
        try:
            return verify_api_key(request, api_key, authorization)
        except Exception:
            logger.exception("Failed to validate API Key")
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
    # If API Key is not present or not valid, attempt to verify the token
    if token:
        try:
            return verify_bearer_token(token)
        except Exception:
            logger.exception("Failed to validate token")
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
    raise HTTPException(status_code=401, detail="Missing authentication credentials")


def verify_token_or_key_single_tenant(
    request: Request,
    api_key: Optional[str] = Security(auth_header),
    authorization: Optional[HTTPAuthorizationCredentials] = Security(http_basic),
    token: Optional[str] = Depends(oauth2_scheme),
) -> str:
    # Attempt to verify API Key first
    if api_key:
        try:
            return verify_api_key_single_tenant(request, api_key, authorization)
        except Exception:
            logger.exception("Failed to validate API Key")
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
    # If API Key is not present or not valid, attempt to verify the token
    if token:
        try:
            return verify_bearer_token_single_tenant(token)
        except Exception:
            logger.exception("Failed to validate token")
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
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
