from typing import Any
from urllib.parse import quote

import httpx


class KeepAPIError(Exception):
    """Raised when keep-backend returns an error or is unreachable."""


def seg(value: str) -> str:
    """Percent-encode a caller-supplied value as a single URL path segment."""
    value = str(value)
    if not value or value in (".", ".."):
        raise ValueError(f"Invalid identifier: {value!r}")
    return quote(value, safe="")


class KeepClient:
    """Thin async wrapper over the Keep REST API. AuthZ stays in keep-backend."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        require_key: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._require_key = require_key
        self._transport = transport

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        api_key: str | None = None,
        public: bool = False,
    ) -> Any:
        key = api_key or self._api_key
        if self._require_key and not key and not public:
            raise KeepAPIError("X-API-KEY header is required")
        headers = {"X-API-KEY": key} if key else {}
        # drop unset params; httpx expands lists into repeated query keys
        params = {k: v for k, v in (params or {}).items() if v is not None}
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
                transport=self._transport,
            ) as http:
                resp = await http.request(
                    method, path, params=params, json=json, headers=headers
                )
        except httpx.HTTPError as exc:
            raise KeepAPIError(f"Could not reach Keep backend: {exc}") from exc
        # redirects are not followed (would leak X-API-KEY); treat as failure
        if resp.status_code >= 300:
            raise KeepAPIError(
                f"Keep API {method} {path} failed with {resp.status_code}: "
                f"{resp.text[:200]}"
            )
        if not resp.content:
            return None
        return resp.json()

    async def get(self, path: str, **kw) -> Any:
        return await self.request("GET", path, **kw)

    async def post(self, path: str, **kw) -> Any:
        return await self.request("POST", path, **kw)
