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
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def validate(self):
        """Validate the provider configuration by fetching the current user profile."""
        try:
            resp = self.session.get(f"{self.api_url}/users/me")
            resp.raise_for_status()
        except Exception as e:
            raise ProviderException(f"Squadcast validation failed: {e}")

    def list_services(self) -> List[Dict[str, Any]]:
        """List Squadcast services."""
        resp = self.session.get(f"{self.api_url}/services")
        resp.raise_for_status()
        return resp.json().get("data", [])

    def trigger_incident(self, service_id: str, title: str, description: str = "", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Trigger an incident in Squadcast."""
        data = {
            "title": title,
            "description": description,
        }
        if payload:
            data.update(payload)
        resp = self.session.post(f"{self.api_url}/incidents", json={
            "service_id": service_id,
            **data
        })
        resp.raise_for_status()
        return resp.json()

    def list_incidents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List incidents, optionally filtered by status (triggered, acknowledged, resolved)."""
        params = {}
        if status:
            params["status"] = status
        resp = self.session.get(f"{self.api_url}/incidents", params=params)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def acknowledge_incident(self, incident_id: str) -> Dict[str, Any]:
        """Acknowledge an incident by ID."""
        resp = self.session.post(f"{self.api_url}/incidents/{incident_id}/acknowledge")
        resp.raise_for_status()
        return resp.json()

    def resolve_incident(self, incident_id: str) -> Dict[str, Any]:
        """Resolve an incident by ID."""
        resp = self.session.post(f"{self.api_url}/incidents/{incident_id}/resolve")
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def from_config(config: Dict[str, Any]):
        api_key = config.get("api_key")
        api_url = config.get("api_url")
        if not api_key:
            raise ProviderException("Squadcast provider requires 'api_key' in config.")
        return SquadcastProvider(api_key=api_key, api_url=api_url)
