import logging
import jwt
from fastapi import Depends, HTTPException
from keep.api.core.config import config
from keep.api.core.db import user_exists, create_user, update_user_last_sign_in, update_user_role
from keep.api.core.dependencies import SINGLE_TENANT_UUID

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.rbac import get_role_by_role_name

logger = logging.getLogger(__name__)

class OneLoginAuthVerifier(AuthVerifierBase):
    """Handles SSO authentication for OneLogin"""

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        self.logger.info(f"Initializing OneLogin AuthVerifier with scopes: {scopes}")
        self.onelogin_issuer = config("ONELOGIN_ISSUER")
        self.onelogin_client_id = config("ONELOGIN_CLIENT_ID")
        self.auto_create_user = config("ONELOGIN_AUTO_CREATE_USER", default=True)

        self.role_mappings = {
            config("ONELOGIN_ADMIN_ROLE", default="keep_admin"): "admin",
            config("ONELOGIN_NOC_ROLE", default="keep_noc"): "noc",
            config("ONELOGIN_WEBHOOK_ROLE", default="keep_webhook"): "webhook",
        }

        if (
            not self.onelogin_issuer
            or not self.onelogin_client_id
        ):
            raise Exception("Missing ONELOGIN_ISSUER or ONELOGIN_CLIENT_ID environment variable")

        # Remove trailing slash if present on issuer
        if self.onelogin_issuer.endswith("/"):
            self.onelogin_issuer = self.onelogin_issuer[:-1]

        self.jwks_url = f"{self.onelogin_issuer}/certs"
        self.jwks_client = jwt.PyJWKClient(self.jwks_url)
        self.logger.info(f"Initialized OneLogin JWKS client with URL: {self.jwks_url}")

        self.logger.info("OneLogin Auth Verifier initialized")

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
                audience= self.onelogin_client_id,
                issuer=self.onelogin_issuer,
                options={"verify_exp": True}
            )

            user_name = payload.get("email") or payload.get("sub") or payload.get("preferred_username")

            onelogin_groups = payload.get("groups", [])
            # When one configures basic roles on OneLogin it comes as a list but when you perform a role mapping it comes as comma separated string
            if type(onelogin_groups) is str:
                onelogin_groups = onelogin_groups.split(",")

            onelogin_groups = [g.strip() for g in onelogin_groups]

            self.logger.debug(f"OneLogin Groups: {onelogin_groups}")

            # Define the priority order of roles
            role_priority = ["admin", "noc", "webhook"]
            mapped_role = None

            self.logger.debug(f"OneLogin to Keep Role Mapping: {self.role_mappings}")

            for role in role_priority:
                self.logger.debug(f"Checking for role {role}")
                for onelogin_grp in onelogin_groups:
                    self.logger.debug(f"Checking for onelogin group {onelogin_grp}")
                    mapped_role_name=self.role_mappings.get(onelogin_grp, "")
                    self.logger.debug(f"Checking for mapped role name {mapped_role_name}")
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
                self.logger.warning(f"No valid role-group mapping found among {onelogin_groups}")
                raise HTTPException(
                    status_code=403,
                    detail=f"No valid role found among {onelogin_groups}",
                )

            # auto provision user
            if self.auto_create_user and not user_exists(
                    tenant_id=SINGLE_TENANT_UUID, username=user_name
            ):
                self.logger.info(f"Auto provisioning user: {user_name}")
                create_user(
                    tenant_id=SINGLE_TENANT_UUID,
                    username=user_name,
                    role=mapped_role.get_name(),
                    password="",
                )
                self.logger.info(f"User {user_name} created")
            elif user_exists(tenant_id=SINGLE_TENANT_UUID, username=user_name):
                # update last login
                self.logger.debug(f"Updating last login for user: {user_name}")
                try:
                    update_user_last_sign_in(
                        tenant_id=SINGLE_TENANT_UUID, username=user_name
                    )
                    self.logger.debug(f"Last login updated for user: {user_name}")
                except Exception:
                    self.logger.warning(f"Failed to update last login for user: {user_name}")
                    pass
                # update role
                self.logger.debug(f"Updating role for user: {user_name}")
                try:
                    update_user_role(
                        tenant_id=SINGLE_TENANT_UUID,
                        username=user_name,
                        role=mapped_role.get_name(),
                    )
                    self.logger.debug(f"Role updated for user: {user_name}")
                except Exception:
                    self.logger.warning(f"Failed to update role for user: {user_name}")
                    pass

            self.logger.info(f"User {user_name} authenticated with role {mapped_role.get_name()}")
            return AuthenticatedEntity(
                tenant_id=SINGLE_TENANT_UUID,
                email=user_name,
                role=mapped_role.get_name(),
                token=token
            )

        except jwt.exceptions.InvalidKeyError as e:
            self.logger.error(f"Invalid key error during token validation: {str(e)}")
            raise HTTPException(status_code=401, detail="Invalid signing key - token validation failed")
        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            self.logger.exception("Failed to validate token")
            raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")
