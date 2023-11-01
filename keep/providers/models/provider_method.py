from typing import Callable

from pydantic import BaseModel


class ProviderMethod(BaseModel):
    """
    Provider "special" method model.
    """

    name: str
    func: Callable
    scopes: list[str] = []  # required scope names, should match ProviderScope names
    description: str | None = None
