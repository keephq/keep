import logging
import os

import jwt
from fastapi import Depends, HTTPException

from keep.api.core.config import config
from keep.api.core.db import (
    create_user,
    update_user_last_sign_in,
    update_user_role,
    user_exists,
)
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme

logger = logging.getLogger(__name__)

DEFAULT_ROLE_NAME = "noc"
ROLE_PRIORITY = ["admin", "noc", "webhook"]


class OktaAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for Okta"""

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        self.okta_issuer = os.environ.get("OKTA_ISSUER")
        self.okta_audience = os.environ.get("OKTA_AUDIENCE")
        self.okta_client_id = os.environ.get("OKTA_CLIENT_ID")
        self.jwks_url = os.environ.get("OKTA_JWKS_URL")

        # If no explicit JWKS URL is provided, we need an issuer to construct it
        if not self.jwks_url and not self.okta_issuer:
            raise Exception("Missing both OKTA_JWKS_URL and OKTA_ISSUER environment variables")

        # Remove trailing slash if present on issuer
        if self.okta_issuer and self.okta_issuer.endswith("/"):
            self.okta_issuer = self.okta_issuer[:-1]

        # Initialize JWKS client - prefer direct JWKS URL if available
        if not self.jwks_url:
            self.jwks_url = f"{self.okta_issuer}/.well-known/jwks.json"

        assert self.jwks_url is not None
        self.jwks_client = jwt.PyJWKClient(self.jwks_url)
        logger.info(f"Initialized JWKS client with URL: {self.jwks_url}")

        # Build group → Keep role mapping from environment variables.
        # OKTA_ADMIN_GROUPS, OKTA_NOC_GROUPS, OKTA_WEBHOOK_GROUPS accept
        # comma-separated Okta group names.
        self.group_mappings: dict[str, str] = {}
        for env_var, target_role in [
            ("OKTA_ADMIN_GROUPS", "admin"),
            ("OKTA_NOC_GROUPS", "noc"),
            ("OKTA_WEBHOOK_GROUPS", "webhook"),
        ]:
            groups_str = config(env_var, default="")
            for group in [g.strip() for g in groups_str.split(",") if g.strip()]:
                self.group_mappings[group] = target_role
        if self.group_mappings:
            logger.info(f"Okta group mappings loaded: {self.group_mappings}")

        self.auto_create_user = config("OKTA_AUTO_CREATE_USER", default=True, cast=bool)

    def _verify_bearer_token(self, token: str = Depends(oauth2_scheme)) -> AuthenticatedEntity:
        if not token:
            raise HTTPException(status_code=401, detail="No token provided")
        
        try:
            # Get the signing key directly from the JWT
            signing_key = self.jwks_client.get_signing_key_from_jwt(token).key
            
            # Decode and verify the token
            payload = jwt.decode(
                token,
                key=signing_key,
                algorithms=["RS256"],
                audience=self.okta_audience or self.okta_client_id,
                issuer=self.okta_issuer,
                options={"verify_exp": True}
            )
            
            tenant_id = payload.get("keep_tenant_id", "keep")
            email = payload.get("email") or payload.get("sub") or payload.get("preferred_username")
            name = payload.get("name") or payload.get("displayName") or email
            groups = payload.get("groups", [])

            logger.info(f"Token claims — email={email}, name={name}, groups={groups}, group_mappings={self.group_mappings}")

            # Explicit claim overrides always take priority
            role_name = payload.get("keep_role") or payload.get("role")

            # If no explicit claim, try to resolve role from Okta groups via
            # the configured OKTA_*_GROUPS mappings (highest privilege wins).
            if not role_name and self.group_mappings and groups:
                for priority_role in ROLE_PRIORITY:
                    for group in groups:
                        if self.group_mappings.get(group) == priority_role:
                            role_name = priority_role
                            logger.info(f"Resolved role '{role_name}' from Okta group '{group}'")
                            break
                    if role_name:
                        break

            # Final fallback: first group as-is, then default role
            if not role_name:
                role_name = (groups[0] if groups else None) or DEFAULT_ROLE_NAME

            logger.info(f"Resolved role='{role_name}' for {email}")

            org_id = payload.get("org_id")
            org_realm = payload.get("org_realm")
            
            if not email:
                raise HTTPException(status_code=401, detail="No email in token")

            # Auto-provision user in Keep's DB on first login, update role/last-login on subsequent ones
            tenant_id_for_db = SINGLE_TENANT_UUID
            logger.info(
                f"User provisioning check — auto_create_user={self.auto_create_user}, "
                f"email={email}, tenant={tenant_id_for_db}, role={role_name}"
            )
            exists = user_exists(tenant_id=tenant_id_for_db, username=email)
            logger.info(f"user_exists({email}) = {exists}")
            if self.auto_create_user and not exists:
                logger.info(f"Auto provisioning Okta user: {email}")
                try:
                    create_user(tenant_id=tenant_id_for_db, username=email, password="", role=role_name)
                    logger.info(f"User {email} created in DB with role {role_name}")
                except Exception:
                    logger.exception(f"Failed to auto-create user {email}")
            elif exists:
                try:
                    update_user_last_sign_in(tenant_id=tenant_id_for_db, username=email)
                    update_user_role(tenant_id=tenant_id_for_db, username=email, role=role_name)
                except Exception:
                    logger.exception(f"Failed to update user {email}")

            logger.info(f"Successfully verified token for user with email: {email}")
            return AuthenticatedEntity(
                tenant_id=tenant_id,
                email=email,
                role=role_name,
                org_id=org_id,
                org_realm=org_realm,
                token=token,
                name=name,
            )
            
        except jwt.exceptions.InvalidKeyError as e:
            logger.error(f"Invalid key error during token validation: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid signing key - token validation failed")
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            logger.exception("Failed to validate token")
            raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}") 