import hashlib
import logging
import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPDigest,
    OAuth2PasswordBearer,
)
from sqlmodel import Session, select
from starlette_context import context

from keep.api.core.db import get_session
from keep.api.models.db.tenant import TenantApiKey

logger = logging.getLogger(__name__)

auth_header = APIKeyHeader(name="X-API-KEY", scheme_name="API Key", auto_error=False)
http_digest = HTTPDigest(
    auto_error=False
)  # hack for grafana, they don't support api key header
http_basic = HTTPBasic(auto_error=False)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Just a fake random tenant id
SINGLE_TENANT_UUID = "keep"
SINGLE_TENANT_EMAIL = "admin@keephq"


def verify_single_tenant() -> str:
    context.data["tenant_id"] = SINGLE_TENANT_UUID
    return SINGLE_TENANT_UUID


def get_user_email_single_tenant() -> str:
    return SINGLE_TENANT_EMAIL


def get_user_email(request: Request) -> str | None:
    token = request.headers.get("Authorization").split(" ")[1]
    decoded_token = jwt.decode(token, options={"verify_signature": False})
    return decoded_token.get("email")


def verify_api_key(
    request: Request,
    api_key: str = Security(auth_header),
    authorization: HTTPAuthorizationCredentials = Security(http_basic),
    session: Session = Depends(get_session),
) -> str:
    """
    Verifies that a customer is allowed to access the API.

    Args:
        api_key (str, optional): The API key extracted from X-API-KEY header. Defaults to Security(auth_header).
        session (Session, optional): A databse session. Defaults to Depends(get_session).

    Raises:
        HTTPException: 401 if the user is unauthorized.

    Returns:
        str: The tenant id.
    """
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
        scheme, _, credentials = auth_header.partition(" ")
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

    api_key_hashed = hashlib.sha256(api_key.encode()).hexdigest()

    statement = select(TenantApiKey).where(TenantApiKey.key_hash == api_key_hashed)
    tenant_api_key = session.exec(statement).first()
    if not tenant_api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    # keep it in the context for later use
    context.data["tenant_id"] = tenant_api_key.tenant_id
    return tenant_api_key.tenant_id


def verify_bearer_token(token: str = Depends(oauth2_scheme)) -> str:
    # Took the implementation from here:
    #   https://github.com/auth0-developer-hub/api_fastapi_python_hello-world/blob/main/application/json_web_token.py
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
        )
        tenant_id = payload.get("keep_tenant_id")
        # keep it in the context for later use
        context.data["tenant_id"] = tenant_id
        return tenant_id
    except Exception as e:
        logger.exception("Failed to validate token")
        raise HTTPException(status_code=401, detail=str(e))
