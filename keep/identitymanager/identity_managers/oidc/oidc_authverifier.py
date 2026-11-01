import logging

import jwt
import requests
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
from keep.identitymanager.rbac import get_role_by_role_name

logger = logging.getLogger(__name__)

# Module-level JWKS client cache. The auth verifier is instantiated per route,
# so without this cache the discovery document would be fetched over HTTP on
# every API request (see Auth0AuthVerifier TODO and keep issue #6781).
_jwks_clients: dict[str, tuple[str, jwt.PyJWKClient]] = {}


def _discover_jwks_uri(issuer: str) -> str:
    """Discover the JWKS URI via the OpenID Connect Discovery endpoint.

    Per the OpenID Connect Discovery 1.0 specification, the ``jwks_uri`` must
    be obtained from the provider's discovery document at
    ``{issuer}/.well-known/openid-configuration``.
    """
    discovery_url = f"{issuer}/.well-known/openid-configuration"
    resp = requests.get(discovery_url, timeout=10, headers={"User-Agent": "keep-api"})
    resp.raise_for_status()
    jwks_uri = resp.json().get("jwks_uri")
    if not jwks_uri:
        raise Exception(
            f"Discovery document at {discovery_url} did not contain jwks_uri"
        )
    return jwks_uri


def _get_jwks_client(issuer: str, jwks_url: str = None) -> tuple[str, jwt.PyJWKClient]:
    """Return a cached (jwks_uri, PyJWKClient) pair for the issuer.

    PyJWKClient(cache_keys=True) re-fetches the JWKS when it encounters an
    unknown ``kid``, so key rotation on the provider side is handled without
    invalidating this cache.
    """
    cache_key = jwks_url or issuer
    if cache_key not in _jwks_clients:
        jwks_uri = jwks_url or _discover_jwks_uri(issuer)
        _jwks_clients[cache_key] = (
            jwks_uri,
            jwt.PyJWKClient(
                jwks_uri, cache_keys=True, headers={"User-Agent": "keep-api"}
            ),
        )
    return _jwks_clients[cache_key]


class OidcAuthVerifier(AuthVerifierBase):
    """Handles SSO authentication for any OpenID Connect provider.

    Verifies RS256-signed id_tokens (default) or access_tokens issued by the
    provider configured via KEEP_OIDC_* environment variables, maps provider
    groups to keep roles and just-in-time provisions users.
    """

    def __init__(self, scopes: list[str] = []) -> None:
        super().__init__(scopes)
        self.logger.info(f"Initializing OIDC AuthVerifier with scopes: {scopes}")
        self.oidc_issuer = config("KEEP_OIDC_ISSUER", default=None)
        self.oidc_client_id = config("KEEP_OIDC_CLIENT_ID", default=None)
        self.oidc_audience = config("KEEP_OIDC_AUDIENCE", default=None)
        self.groups_claim = config("KEEP_OIDC_GROUPS_CLAIM", default="groups")
        self.auto_create_user = config("KEEP_OIDC_AUTO_CREATE_USER", default=True)

        if not self.oidc_issuer or not self.oidc_client_id:
            raise Exception(
                "Missing KEEP_OIDC_ISSUER or KEEP_OIDC_CLIENT_ID environment variable"
            )

        # Remove trailing slash if present on issuer
        if self.oidc_issuer.endswith("/"):
            self.oidc_issuer = self.oidc_issuer[:-1]

        # For id_tokens the OIDC spec guarantees aud=client_id, so client_id is
        # the default audience. KEEP_OIDC_AUDIENCE overrides it for providers
        # whose access tokens must be validated instead (e.g. aud="account"
        # in Keycloak access tokens).
        self.token_audience = self.oidc_audience or self.oidc_client_id

        # Comma separated group lists -> {group: keep role} mappings
        self.role_mappings = {}
        for env_var, target_role in [
            ("KEEP_OIDC_ADMIN_ROLES", "admin"),
            ("KEEP_OIDC_NOC_ROLES", "noc"),
            ("KEEP_OIDC_WEBHOOK_ROLES", "webhook"),
        ]:
            roles_str = config(env_var, default="")
            for group in roles_str.split(","):
                group = group.strip()
                if group:
                    self.role_mappings[group] = target_role

        # The JWKS client is created lazily on the first token verification:
        # this verifier is instantiated at route import time, and a discovery
        # round-trip there would make app startup depend on IdP availability.
        self.jwks_url_override = config("KEEP_OIDC_JWKS_URL", default=None)
        self.jwks_client = None
        self.logger.info(
            f"Initialized OIDC AuthVerifier for issuer {self.oidc_issuer} "
            f"(JWKS client is lazy)"
        )
        self.logger.info("OIDC Auth Verifier initialized")

    def _get_signing_key(self, token: str) -> str:
        if self.jwks_client is None:
            self.jwks_uri, self.jwks_client = _get_jwks_client(
                self.oidc_issuer, self.jwks_url_override
            )
            self.logger.info(f"Initialized OIDC JWKS client with URL: {self.jwks_uri}")
        return self.jwks_client.get_signing_key_from_jwt(token).key

    def _verify_bearer_token(
        self, token: str = Depends(oauth2_scheme)
    ) -> AuthenticatedEntity:
        if not token:
            raise HTTPException(status_code=401, detail="No token provided")
        try:
            # Get the signing key directly from the JWT
            signing_key = self._get_signing_key(token)

            # Decode and verify the token
            payload = jwt.decode(
                token,
                key=signing_key,
                algorithms=["RS256"],
                audience=self.token_audience,
                issuer=self.oidc_issuer,
                leeway=60,
                options={"verify_exp": True},
            )

            user_name = (
                payload.get("email")
                or payload.get("preferred_username")
                or payload.get("sub")
            )

            oidc_groups = payload.get(self.groups_claim, [])
            # Providers send groups as a list, a single string or a comma
            # separated string - normalize to a list
            if isinstance(oidc_groups, str):
                oidc_groups = oidc_groups.split(",")
            oidc_groups = [
                group.strip() for group in oidc_groups if isinstance(group, str)
            ]

            self.logger.debug(f"OIDC Groups: {oidc_groups}")

            # Define the priority order of roles
            role_priority = ["admin", "noc", "webhook"]
            mapped_role = None

            self.logger.debug(f"OIDC to Keep Role Mapping: {self.role_mappings}")

            for role in role_priority:
                self.logger.debug(f"Checking for role {role}")
                for oidc_grp in oidc_groups:
                    mapped_role_name = self.role_mappings.get(oidc_grp, "")
                    if role == mapped_role_name:
                        try:
                            mapped_role = get_role_by_role_name(mapped_role_name)
                            break
                        except HTTPException:
                            continue
                if mapped_role:
                    break

            # if no valid role was found, throw a 403 exception
            if not mapped_role:
                self.logger.warning(
                    f"No valid role-group mapping found among {oidc_groups}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"No valid role found among {oidc_groups}",
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
                # update last sign in and role on every request so a group
                # change on the provider takes effect without re-login
                try:
                    update_user_last_sign_in(
                        tenant_id=SINGLE_TENANT_UUID, username=user_name
                    )
                except Exception:
                    self.logger.warning(
                        f"Failed to update last sign in for user: {user_name}"
                    )
                try:
                    update_user_role(
                        tenant_id=SINGLE_TENANT_UUID,
                        username=user_name,
                        role=mapped_role.get_name(),
                    )
                except Exception:
                    self.logger.warning(f"Failed to update role for user: {user_name}")

            self.logger.info(
                f"User {user_name} authenticated with role {mapped_role.get_name()}"
            )
            return AuthenticatedEntity(
                tenant_id=SINGLE_TENANT_UUID,
                email=user_name,
                role=mapped_role.get_name(),
                token=token,
            )

        except jwt.ExpiredSignatureError:
            self.logger.warning("Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            self.logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except HTTPException:
            raise
        except Exception as e:
            self.logger.exception("Failed to validate token")
            raise HTTPException(
                status_code=401, detail=f"Token validation failed: {str(e)}"
            )
