from typing import Optional

from pydantic import AnyUrl, HttpUrl, conint, errors
from pydantic.networks import Parts


class HttpsUrl(HttpUrl):
    scheme = {"https"}

    @staticmethod
    def get_default_parts(parts):
        return {"port": "443"}


UrlPort = conint(ge=1, le=65_535)


class NoSchemeUrl(AnyUrl):
    """Override to allow url without a scheme."""

    @classmethod
    def build(
        cls,
        *,
        scheme: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: str,
        port: Optional[str] = None,
        path: Optional[str] = None,
        query: Optional[str] = None,
        fragment: Optional[str] = None,
        **_kwargs: str,
    ) -> str:
        url = super().build(
            scheme=scheme,
            user=user,
            password=password,
            host=host,
            port=port,
            path=path,
            query=query,
            fragment=fragment,
            **_kwargs,
        )
        return url.split("://")[1]

    @classmethod
    def validate_parts(cls, parts: Parts, validate_port: bool = True) -> Parts:
        """
        In this override, we removed validation for url scheme.
        """

        parts["scheme"] = "foo"

        if validate_port:
            cls._validate_port(parts["port"])

        user = parts["user"]
        if cls.user_required and user is None:
            raise errors.UrlUserInfoError()

        return parts
