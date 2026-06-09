import requests
from typing import Any, Dict, List, Optional

from keep.providers.base.base_provider import BaseProvider
from keep.exceptions.provider import ProviderException

class SquadcastProvider(BaseProvider):
    """
    Squadcast incident management provider for Keep.
    """
    def __init__(self, api_key: str, api_url: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.api_url = api_url or "https://api.squadcast.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.api_url}{endpoint}"
        try:
            resp = requests.request(method, url, headers=self.headers, timeout=10, **kwargs)
            resp.raise_for_status()
            if resp.content:
                return resp.json()
            return None
        except requests.RequestException as e:
            raise ProviderException(f"Squadcast API error: {e}")

    def list_services(self) -> List[Dict[str, Any]]:
        """List Squadcast services."""
        return self._request("GET", "/services")

    def list_incidents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List Squadcast incidents. Optionally filter by status (triggered, acknowledged, resolved)."""
        params = {"status": status} if status else {}
        return self._request("GET", "/incidents", params=params)

    def create_incident(self, service_id: str, title: str, message: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new incident in Squadcast."""
        data = {
            "service_id": service_id,
            "title": title,
            "message": message,
        }
        if payload:
            data["payload"] = payload
        return self._request("POST", "/incidents", json=data)

    def resolve_incident(self, incident_id: str) -> Dict[str, Any]:
        """Resolve an incident by ID."""
        return self._request("POST", f"/incidents/{incident_id}/resolve")

    def acknowledge_incident(self, incident_id: str) -> Dict[str, Any]:
        """Acknowledge an incident by ID."""
        return self._request("POST", f"/incidents/{incident_id}/acknowledge")

    @staticmethod
    def from_config(config: Dict[str, Any]) -> "SquadcastProvider":
        api_key = config.get("api_key")
        api_url = config.get("api_url")
        if not api_key:
            raise ProviderException("Squadcast API key is required in config.")
        return SquadcastProvider(api_key=api_key, api_url=api_url)
