from keep.identitymanager.authenticatedentity import AuthenticatedEntity
from keep.identitymanager.authverifierbase import AuthVerifierBase


class AzureadAuthVerifier(AuthVerifierBase):
    """Handles authentication and authorization for azuread"""

    def __init__(self, scopes: list[str] = []) -> None:
        pass

    def _verify_bearer_token(self, token) -> AuthenticatedEntity:
        pass
