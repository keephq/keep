from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class KeepAPIError(RuntimeError):
    """Raised when keep-backend returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str, url: str):
        self.status_code = status_code
        self.detail = detail
        self.url = url
        super().__init__(f"{status_code} from {url}: {detail}")


class KeepClient:
    """Async httpx wrapper around the Keep REST API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("KEEP_MCP_KEEP_API_KEY is required")
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers={
                "X-API-KEY": api_key,
                "Accept": "application/json",
                "User-Agent": "keep-mcp/0.1",
            },
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise KeepAPIError(0, f"transport error: {exc}", path) from exc

        if response.status_code >= 400:
            detail = _extract_detail(response)
            raise KeepAPIError(response.status_code, detail, path)

        if not response.content:
            return None
        return response.json()

    # --- alerts ---

    async def query_alerts(
        self,
        cel: str = "",
        limit: int = 25,
        offset: int = 0,
    ) -> dict[str, Any]:
        body = {"cel": cel or "", "limit": limit, "offset": offset}
        return await self._request("POST", "/alerts/query", json=body)

    async def get_alerts_by_fingerprints(
        self, fingerprints: list[str]
    ) -> list[dict[str, Any]]:
        return await self._request(
            "POST", "/alerts/batch", json={"fingerprints": fingerprints}
        )

    # --- incidents ---

    async def list_incidents(
        self,
        status: list[str] | None = None,
        severity: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        cel: str | None = None,
    ) -> dict[str, Any]:
        params: list[tuple[str, str | int]] = [("limit", limit), ("offset", offset)]
        for s in status or []:
            params.append(("status", s))
        for s in severity or []:
            params.append(("severity", s))
        if cel:
            params.append(("cel", cel))
        return await self._request("GET", "/incidents", params=params)

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/incidents/{incident_id}")

    async def get_incident_alerts(
        self, incident_id: str, limit: int = 25, offset: int = 0
    ) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/incidents/{incident_id}/alerts",
            params={"limit": limit, "offset": offset},
        )

    # --- topology ---

    async def get_topology(self, service: str | None = None) -> list[dict[str, Any]]:
        params = {"service": service} if service else None
        return await self._request("GET", "/topology", params=params)

    # --- health ---

    async def ping(self) -> bool:
        try:
            resp = await self._client.get("/healthcheck")
            return resp.status_code < 500
        except httpx.HTTPError:
            return False


def _extract_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            return str(data.get("detail") or data)
        return str(data)
    except ValueError:
        return response.text[:500]
