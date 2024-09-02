from typing import Optional

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass


@dataclass(config=ConfigDict(extra="allow"))
class AuthenticatedEntity:
    """
    Represents an authenticated entity in the system.

    This class is designed to be expandable. Different identity providers can
    add additional fields as needed. For example, a Keycloak implementation
    might add an 'org_id' field.

    Attributes:
        tenant_id (str): The ID of the tenant this entity belongs to.
        email (str): The email address of the authenticated entity.
        api_key_name (Optional[str]): The name of the API key used for authentication, if applicable.
        role (Optional[str]): The role of the authenticated entity, if applicable.

    Note:
        The `config=ConfigDict(extra="allow")` parameter allows for additional
        attributes to be added dynamically, making this class flexible for
        different authentication implementations.
    """

    tenant_id: str
    email: str
    api_key_name: Optional[str] = None
    role: Optional[str] = None
