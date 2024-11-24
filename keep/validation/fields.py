from typing import Optional

from pydantic import AnyUrl, HttpUrl, conint, errors
from pydantic.networks import Parts

UrlPort = conint(ge=1, le=65_535)


class HttpsUrl(HttpUrl):
    """Validate https url, coerce if no scheme, throw if wrong scheme."""

    allowed_schemes = {"https"}

    def __new__(cls, url: Optional[str], **kwargs) -> object:
        _url = url if url is not None and url.startswith("https://") else None
        return super().__new__(cls, _url, **kwargs)

    @staticmethod
    def get_default_parts(parts: Parts) -> Parts:
        return {"scheme": "https", "port": "443"}


class NoSchemeUrl(AnyUrl):
    """Validate url with any scheme, remove scheme in output."""

    def __new__(cls, url: Optional[str], **kwargs) -> object:
        _url = cls.build(**kwargs) if url is None else url
        _url = _url.split("://")[1] if "://" in _url else _url
        return super().__new__(cls, _url, **kwargs)

    @classmethod
    def validate_parts(cls, parts: Parts, validate_port: bool = True) -> Parts:
        """
        In this override, we removed validation for url scheme.
        """

        scheme = parts["scheme"]
        parts["scheme"] = "foo" if scheme is None else scheme

        if validate_port:
            cls._validate_port(parts["port"])

        user = parts["user"]
        if cls.user_required and user is None:
            raise errors.UrlUserInfoError()

        return parts
