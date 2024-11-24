from typing import Optional

from pydantic import AnyUrl, HttpUrl, conint, errors
from pydantic.networks import MultiHostDsn, Parts

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


class MultiHostUrl(MultiHostDsn):
    @classmethod
    def build(
        cls,
        *,
        scheme: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[str] = None,
        path: Optional[str] = None,
        query: Optional[str] = None,
        fragment: Optional[str] = None,
        **_kwargs: str,
    ) -> str:
        hosts = _kwargs.get("hosts")
        if host is not None and hosts is None:
            return super().build(
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
        urls = [
            cls._build_single_url(
                position=-1 if len(hosts) - idx == 1 else idx,
                scheme=scheme,
                user=user,
                password=password,
                host=hp["host"] + (hp["tld"] if hp["host_type"] == "domain" else ""),
                port=hp["port"],
                path=path,
                query=query,
                fragment=fragment,
                **_kwargs,
            )
            for (idx, hp) in enumerate(hosts)
        ]
        return ",".join(urls)

    @classmethod
    def _build_single_url(
        cls,
        *,
        position: int,
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
        parts = Parts(
            scheme=scheme,
            user=user,
            password=password,
            host=host,
            port=port,
            path=path,
            query=query,
            fragment=fragment,
            **_kwargs,  # type: ignore[misc]
        )

        url = ""
        if position == 0:
            url = scheme + "://"
            if user:
                url += user
            if password:
                url += ":" + password
            if user or password:
                url += "@"

        url += host
        if port and (
            "port" not in cls.hidden_parts
            or cls.get_default_parts(parts).get("port") != port
        ):
            url += ":" + port

        if position == -1:
            if path:
                url += path
            if query:
                url += "?" + query
            if fragment:
                url += "#" + fragment
        return url


class NoSchemeMultiHostUrl(MultiHostUrl):
    def __new__(cls, url: Optional[str], **kwargs) -> object:
        _url = cls.build(**kwargs) if url is None else url
        _url = _url.split("://")[1] if "://" in _url else _url
        return super().__new__(cls, _url, **kwargs)

    @classmethod
    def validate_parts(cls, parts: Parts, validate_port: bool = True) -> Parts:
        """
        Remove validation for url scheme, port & user.
        """
        scheme = parts["scheme"]
        parts["scheme"] = "" if scheme is None else scheme

        return parts
