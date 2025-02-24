import hashlib
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
import requests
from fastapi import Depends, HTTPException
from jwt import PyJWK
from jwt.exceptions import (
    ExpiredSignatureError,
    InvalidIssuedAtError,
    InvalidIssuerError,
    InvalidTokenError,
    MissingRequiredClaimError,
)

from keep.api.core.db import create_user, update_user_last_sign_in, user_exists
from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from keep.identitymanager.rbac import Admin as AdminRole
from keep.identitymanager.rbac import Noc as NOCRole
from keep.identitymanager.rbac import get_role_by_role_name

logger = logging.getLogger(__name__)


class AzureADGroupMapper:
    """Maps Azure AD groups to Keep roles"""

    def __init__(self):
        # Get group IDs from environment variables
        self.admin_group_id = os.environ.get("KEEP_AZUREAD_ADMIN_GROUP_ID")
        self.noc_group_id = os.environ.get("KEEP_AZUREAD_NOC_GROUP_ID")

        if not all([self.admin_group_id, self.noc_group_id]):
            raise Exception(
                "Missing KEEP_AZUREAD_ADMIN_GROUP_ID or KEEP_AZUREAD_NOC_GROUP_ID environment variables"
            )

        # Define group to role mapping
        self.group_role_mapping = {
            self.admin_group_id: AdminRole.get_name(),
            self.noc_group_id: NOCRole.get_name(),
        }

    def get_role_from_groups(self, groups: List[str]) -> Optional[str]:
        """
        Determine Keep role based on Azure AD group membership
        Returns highest privilege role if user is in multiple groups
        """
        user_roles = set()
        for group_id in groups:
            if role := self.group_role_mapping.get(group_id):
                user_roles.add(role)

        # If user is in admin group, return admin role
        if AdminRole.get_name() in user_roles:
            return AdminRole.get_name()
        # If user is in NOC group, return NOC role
        elif NOCRole.get_name() in user_roles:
            return NOCRole.get_name()
        # No matching groups
        return None


class AzureADKeysManager:
    """Singleton class to manage Azure AD signing keys"""

    _instance = None
    _signing_keys: Dict[str, Any] = {}
    _last_updated: Optional[datetime] = None
    _cache_duration = timedelta(hours=24)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AzureADKeysManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._last_updated is None:
            self.tenant_id = os.environ.get("KEEP_AZUREAD_TENANT_ID")
            if not self.tenant_id:
                raise Exception("Missing KEEP_AZUREAD_TENANT_ID environment variable")
            self.jwks_uri = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
            self._refresh_keys()

    def _refresh_keys(self) -> None:
        """Fetch signing keys from Azure AD's JWKS endpoint"""
        try:
            response = requests.get(self.jwks_uri)
            response.raise_for_status()
            jwks = response.json()

            new_keys = {}
            for key in jwks.get("keys", []):
                if key.get("use") == "sig":  # Only use signing keys
                    logger.debug("Loading public key from certificate: %s", key)
                    cert_obj = PyJWK(key, "RS256")
                    if kid := key.get("kid"):
                        new_keys[kid] = cert_obj.key

            if new_keys:  # Only update if we got valid keys
                self._signing_keys = new_keys
                self._last_updated = datetime.utcnow()
                logger.info("Successfully refreshed Azure AD signing keys")
            else:
                logger.error("No valid signing keys found in JWKS response")

        except requests.RequestException as e:
            logger.error(f"Failed to fetch signing keys: {str(e)}")
            if not self._signing_keys:
                raise HTTPException(
                    status_code=500, detail="Unable to verify tokens at this time"
                )

    def get_signing_key(self, kid: str) -> Optional[Any]:
        """Get a signing key by its ID, refreshing if necessary"""
        now = datetime.utcnow()

        # Refresh keys if they're expired or if we can't find the requested key
        if (
            self._last_updated is None
            or now - self._last_updated > self._cache_duration
            or (kid not in self._signing_keys)
        ):
            self._refresh_keys()

        return self._signing_keys.get(kid)


# Initialize the keys manager globally
azure_keys_manager = AzureADKeysManager()


class AzureadAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for Azure AD"""

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        # Azure AD configurations
        self.tenant_id = os.environ.get("KEEP_AZUREAD_TENANT_ID")
        self.client_id = os.environ.get("KEEP_AZUREAD_CLIENT_ID")

        if not all([self.tenant_id, self.client_id]):
            raise Exception(
                "Missing KEEP_AZUREAD_TENANT_ID or KEEP_AZUREAD_CLIENT_ID environment variable"
            )

        self.group_mapper = AzureADGroupMapper()
        # Keep track of hashed tokens so we won't update the user on the same token
        self.saw_tokens = set()

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        """Verify the Azure AD JWT token and extract claims"""

        try:
            # First decode without verification to get the key id (kid)
            unverified_headers = jwt.get_unverified_header(token)
            kid = unverified_headers.get("kid")

            if not kid:
                raise HTTPException(status_code=401, detail="No key ID in token header")

            # Get the signing key from the global manager
            signing_key = azure_keys_manager.get_signing_key(kid)
            if not signing_key:
                raise HTTPException(status_code=401, detail="Invalid token signing key")

            # For v2.0 tokens, 'appid' doesn't exist — 'azp' is used instead.
            # Remove "appid" from the 'require' list so v2 tokens won't fail.
            options = {
                "verify_signature": True,
                "verify_aud": False,  # We'll validate manually below
                "verify_iat": True,
                "verify_exp": True,
                "verify_nbf": True,
                # we will validate manually since we need to support both
                # v1 (sts.windows.net) and v2 (https://login.microsoftonline.com)
                "verify_iss": False,
                # "require" the standard claims but NOT "appid" (search for 'azp' in this code to see the comment)
                "require": ["exp", "iat", "nbf", "iss", "sub"],
            }

            try:

                payload = jwt.decode(
                    token,
                    key=signing_key,
                    algorithms=["RS256"],
                    options=options,
                )

                # ---- MANUAL ISSUER CHECK ----
                # Allowed issuers for v1 vs. v2 in the same tenant:
                allowed_issuers = [
                    f"https://sts.windows.net/{self.tenant_id}/",  # v1 tokens
                    f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",  # v2 tokens
                ]
                issuer_in_token = payload.get("iss")
                if issuer_in_token not in allowed_issuers:
                    raise HTTPException(status_code=401, detail="Invalid token issuer")

                # Check client ID: v1 -> 'appid', v2 -> 'azp'
                client_id_in_token = payload.get("appid") or payload.get("azp")

                if not client_id_in_token:
                    raise HTTPException(
                        status_code=401, detail="No client ID (appid/azp) in token"
                    )

                if client_id_in_token != self.client_id:
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid token application ID (appid/azp)",
                    )

                # Validate the audience
                allowed_aud = [
                    f"api://{self.client_id}",  # v1 tokens
                    f"{self.client_id}",  # v2 tokens
                ]
                if payload.get("aud") not in allowed_aud:
                    self.logger.error(
                        f"Invalid token audience: {payload.get('aud')}",
                        extra={
                            "tenant_id": self.tenant_id,
                            "audience": payload.get("aud"),
                            "allowed_aud": allowed_aud,
                        },
                    )
                    raise HTTPException(
                        status_code=401, detail="Invalid token audience"
                    )

            except ExpiredSignatureError:
                raise HTTPException(status_code=401, detail="Token has expired")
            except InvalidIssuerError:
                raise HTTPException(status_code=401, detail="Invalid token issuer")
            except (InvalidIssuedAtError, MissingRequiredClaimError):
                raise HTTPException(
                    status_code=401, detail="Token is missing required claims"
                )
            except InvalidTokenError as e:
                logger.error(f"Token validation failed: {str(e)}")
                raise HTTPException(status_code=401, detail="Invalid token")

            # Extract relevant claims
            tenant_id = payload.get("tid")
            email = (
                payload.get("email")
                or payload.get("preferred_username")
                or payload.get("unique_name")
            )

            if not all([tenant_id, email]):
                raise HTTPException(status_code=401, detail="Missing required claims")

            # Clean up email if it's in the live.com#email@domain.com format
            if "#" in email:
                email = email.split("#")[1]

            # Get groups from token
            groups = payload.get("groups", [])

            # Map groups to role
            role_name = self.group_mapper.get_role_from_groups(groups)
            if not role_name:
                self.logger.warning(
                    f"User {email} is not a member of any authorized groups for Keep",
                    extra={
                        "tenant_id": tenant_id,
                        "groups": groups,
                    },
                )
                raise HTTPException(
                    status_code=403,
                    detail="User not a member of any authorized groups for Keep",
                )

            # Validate role scopes
            role = get_role_by_role_name(role_name)
            if not role.has_scopes(self.scopes):
                self.logger.warning(
                    f"Role {role_name} does not have required permissions",
                    extra={
                        "tenant_id": tenant_id,
                        "role": role_name,
                    },
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Role {role_name} does not have required permissions",
                )

            # Auto-provisioning logic
            hashed_token = hashlib.sha256(token.encode()).hexdigest()
            if hashed_token not in self.saw_tokens and not user_exists(
                tenant_id, email
            ):
                create_user(
                    tenant_id=tenant_id, username=email, role=role_name, password=""
                )

            if hashed_token not in self.saw_tokens:
                update_user_last_sign_in(tenant_id, email)
            self.saw_tokens.add(hashed_token)

            return AuthenticatedEntity(tenant_id, email, None, role_name)

        except HTTPException:
            # Re-raise known HTTP errors
            self.logger.exception("Token validation failed (HTTPException)")
            raise
        except Exception:
            self.logger.exception("Token validation failed")
            raise HTTPException(status_code=401, detail="Invalid token")

    def _authorize(self, authenticated_entity: AuthenticatedEntity) -> None:
        """
        Authorize the authenticated entity against required scopes
        """
        if not authenticated_entity.role:
            raise HTTPException(status_code=403, detail="No role assigned")

        role = get_role_by_role_name(authenticated_entity.role)
        if not role.has_scopes(self.scopes):
            raise HTTPException(
                status_code=403,
                detail="You don't have the required permissions to access this resource",
            )
