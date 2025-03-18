# filepath: /providers/nagios_provider.py
import requests

class NagiosProvider:
    def __init__(self, base_url, api_key):
        """
        Initialize the Nagios Provider with the base URL and API key.
        """
        self.base_url = base_url
        self.api_key = api_key

    def fetch_alerts(self):
        """
        Fetch alerts from Nagios.
        """
        try:
            response = requests.get(
                f"{self.base_url}/alerts",
                headers={"Authorization": f"Bearer {self.api_key}"}
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching alerts: {e}")
            return None