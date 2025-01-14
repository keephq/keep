from typing import Literal

from pydantic import BaseModel


class ProviderMethodParam(BaseModel):
    """
    Just a simple model to represent a provider method parameter
    """

    name: str
    type: str
    mandatory: bool = True
    default: str | None = None
    expected_values: list[str] | None = (
        None  # for example if type is Literal or something
    )


class ProviderMethod(BaseModel):
    """
    Provider "special" method model.
    """

    name: str
    func_name: str  # the name of the function in the provider class
    scopes: list[str] = []  # required scope names, should match ProviderScope names
    description: str | None = None
    category: str | None = None
    type: Literal["view", "action"] = "view"


class ProviderMethodDTO(ProviderMethod):
    """
    Constructred in providers_factory, this includes the paramters the function receives
        We use this to generate the UI for the provider method
        This is populated using reflection from the function signature
    """

    func_params: list[ProviderMethodParam] = []
