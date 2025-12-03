import logging
import jwt
from fastapi import Depends, HTTPException
from keep.api.core.config import config
from keep.api.core.db import (
    user_exists,
    create_user,
    update_user_last_sign_in,
    update_user_role,
)
from keep.api.core.dependencies import SINGLE_TENANT_UUID
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.rbac import get_role_by_role_name

logger = logging.getLogger(__name__)


class OktaAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for Okta"""

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        self.logger.info(f"Initializing Okta AuthVerifier with scopes: {scopes}")
        self.okta_issuer = config("OKTA_ISSUER")
        self.okta_audience = config("OKTA_AUDIENCE")
        self.okta_client_id = config("OKTA_CLIENT_ID")
        self.jwks_url = config("OKTA_JWKS_URL")
        self.auto_create_user = config("OKTA_AUTO_CREATE_USER", default=True)

        self.role_mappings = {
            config("OKTA_ADMIN_ROLE", default="keep_admin"): "admin",
            config("OKTA_NOC_ROLE", default="keep_noc"): "noc",
            config("OKTA_WEBHOOK_ROLE", default="keep_webhook"): "webhook",
        }

        # If no explicit JWKS URL is provided, we need an issuer to construct it
        if not self.jwks_url and not self.okta_issuer:
            raise Exception(
                "Missing both OKTA_JWKS_URL and OKTA_ISSUER environment variables"
            )

        # Remove trailing slash if present on issuer
        if self.okta_issuer and self.okta_issuer.endswith("/"):
            self.okta_issuer = self.okta_issuer[:-1]

        # Initialize JWKS client - prefer direct JWKS URL if available
        if not self.jwks_url:
            self.jwks_url = f"{self.okta_issuer}/v1/keys"

        # At this point, self.jwks_url is guaranteed to be a string
        assert self.jwks_url is not None
        self.jwks_client = jwt.PyJWKClient(self.jwks_url)
        self.logger.info(f"Initialized Okta JWKS client with URL: {self.jwks_url}")

        self.logger.info("Okta Auth Verifier initialized")

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
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
                options={"verify_exp": True},
            )

            # Extract user info from token with simplified role handling
            tenant_id = payload.get(
                "keep_tenant_id", SINGLE_TENANT_UUID
            )  # Default to SINGLE_TENANT_UUID if not specified
            user_name = (
                payload.get("email")
                or payload.get("sub")
                or payload.get("preferred_username")
            )

            okta_groups = payload.get("groups", [])

            okta_groups = [g.strip() for g in okta_groups]

            self.logger.debug(f"Okta Groups: {okta_groups}")

            # Define the priority order of roles
            role_priority = ["admin", "noc", "webhook"]
            mapped_role = None

            self.logger.debug(f"Okta to Keep Role Mapping: {self.role_mappings}")

            for role in role_priority:
                self.logger.debug(f"Checking for role {role}")
                for okta_group in okta_groups:
                    self.logger.debug(f"Checking for okta group {okta_group}")
                    mapped_role_name = self.role_mappings.get(okta_group, "")
                    self.logger.debug(
                        f"Checking for mapped role name {mapped_role_name}"
                    )
                    if role == mapped_role_name:
                        try:
                            self.logger.debug(f"Getting role {mapped_role_name}")
                            mapped_role = get_role_by_role_name(mapped_role_name)
                            self.logger.debug(f"Role {mapped_role_name} found")
                            break
                        except HTTPException:
                            self.logger.debug(f"Role {mapped_role_name} not found")
                            continue
                if mapped_role:
                    self.logger.debug(f"Role {mapped_role.get_name()} found")
                    break
            # if no valid role was found, throw a 403 exception
            if not mapped_role:
                self.logger.warning(
                    f"No valid role-group mapping found among {okta_groups}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"No valid role found among {okta_groups}",
                )

            if not user_name:
                raise HTTPException(status_code=401, detail="No user name in token")

            # auto provision user
            if self.auto_create_user and not user_exists(
                tenant_id=tenant_id, username=user_name
            ):
                self.logger.info(f"Auto provisioning user: {user_name}")
                create_user(
                    tenant_id=tenant_id,
                    username=user_name,
                    role=mapped_role.get_name(),
                    password="",
                )
                self.logger.info(f"User {user_name} created")
            elif user_exists(tenant_id=tenant_id, username=user_name):
                # update last login
                self.logger.debug(f"Updating last login for user: {user_name}")
                try:
                    update_user_last_sign_in(tenant_id=tenant_id, username=user_name)
                    self.logger.debug(f"Last login updated for user: {user_name}")
                except Exception:
                    self.logger.warning(
                        f"Failed to update last login for user: {user_name}"
                    )
                    pass
                # update role
                self.logger.debug(f"Updating role for user: {user_name}")
                try:
                    update_user_role(
                        tenant_id=tenant_id,
                        username=user_name,
                        role=mapped_role.get_name(),
                    )
                    self.logger.debug(f"Role updated for user: {user_name}")
                except Exception:
                    self.logger.warning(f"Failed to update role for user: {user_name}")
                    pass

            self.logger.info(
                f"User {user_name} authenticated with role {mapped_role.get_name()}"
            )
            return AuthenticatedEntity(
                tenant_id=tenant_id,
                email=user_name,
                role=mapped_role.get_name(),
                token=token,
            )

        except jwt.exceptions.InvalidKeyError as e:
            self.logger.error(f"Invalid key error during token validation: {str(e)}")
            raise HTTPException(
                status_code=401, detail="Invalid signing key - token validation failed"
            )
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            self.logger.exception("Failed to validate token")
            raise HTTPException(
                status_code=401, detail=f"Token validation failed: {str(e)}"
            )
