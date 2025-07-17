import logging
import os

import jwt
import requests
from fastapi import Depends, HTTPException

from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase, oauth2_scheme
from jwt.algorithms import RSAAlgorithm

logger = logging.getLogger(__name__)

# Define constant locally instead of importing it
DEFAULT_ROLE_NAME = "user"  # Default role name for user access

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
        
        # At this point, self.jwks_url is guaranteed to be a string
        assert self.jwks_url is not None
        self.jwks_client = jwt.PyJWKClient(self.jwks_url)
        logger.info(f"Initialized JWKS client with URL: {self.jwks_url}")

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
            
            # Extract user info from token with simplified role handling
            tenant_id = payload.get("keep_tenant_id", "keep")  # Default to 'keep' if not specified
            email = payload.get("email") or payload.get("sub") or payload.get("preferred_username")
            
            # Look for role in standard locations with a default of "user"
            role_name = (
                payload.get("keep_role") or 
                payload.get("role") or
                payload.get("groups", [None])[0] or
                DEFAULT_ROLE_NAME  # Use constant for consistency
            )
            
            org_id = payload.get("org_id")
            org_realm = payload.get("org_realm")
            
            if not email:
                raise HTTPException(status_code=401, detail="No email in token")
            
            logger.info(f"Successfully verified token for user with email: {email}")
            return AuthenticatedEntity(
                tenant_id=tenant_id,
                email=email,
                role=role_name,
                org_id=org_id,
                org_realm=org_realm,
                token=token
            )
            
        except jwt.exceptions.InvalidKeyError:
            # Refresh the JWKS and try again
            logger.warning("Invalid key error, refreshing JWKS")
            self.jwks_client = jwt.PyJWKClient(self.jwks_url)
            # Try again with the refreshed client
            return self._verify_bearer_token(token)
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            logger.exception("Failed to validate token")
            raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}") 