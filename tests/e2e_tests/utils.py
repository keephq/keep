from keep.providers.providers_factory import ProvidersFactory
import requests


def trigger_alert(provider_name):
    provider = ProvidersFactory.get_provider_class(provider_name)
    requests.post(
        f"http://localhost:8080/alerts/event/{provider_name}",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": "3db87031-41c7-43cf-9a20-7cdbcf32f97d",
        },
        json=provider.simulate_alert(),
    )
