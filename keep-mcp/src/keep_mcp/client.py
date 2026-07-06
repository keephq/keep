from __future__ import annotations

from typing import Any

import httpx


class KeepClient:
    """Async httpx wrapper around the Keep REST API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0):
        if not api_key:
            raise ValueError("KEEP_MCP_KEEP_API_KEY is required")
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"X-API-KEY": api_key, "User-Agent": "keep-mcp/0.1"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = await self._client.request(method, path, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.content else None

    async def query_alerts(self, cel: str = "", limit: int = 25, offset: int = 0) -> dict[str, Any]:
        return await self._request(
            "POST", "/alerts/query", json={"cel": cel, "limit": limit, "offset": offset}
        )

    async def list_incidents(
        self,
        status: list[str] | None = None,
        severity: list[str] | None = None,
        limit: int = 25,
        offset: int = 0,
        cel: str | None = None,
    ) -> dict[str, Any]:
        params: list[tuple[str, str | int]] = [("limit", limit), ("offset", offset)]
        params += [("status", s) for s in status or []]
        params += [("severity", s) for s in severity or []]
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

    async def get_topology(self, service: str | None = None) -> list[dict[str, Any]]:
        return await self._request(
            "GET", "/topology", params={"service": service} if service else None
        )

    async def get(self, path: str) -> httpx.Response:
        """Raw GET, used by /readyz to probe upstream health."""
        return await self._client.get(path)
