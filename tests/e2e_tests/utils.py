from keep.providers.providers_factory import ProvidersFactory
import requests


def trigger_alert(provider_name):
    provider = ProvidersFactory.get_provider_class(provider_name)
    requests.post(
        f"http://localhost:8080/alerts/event/{provider_name}",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": "really_random_secret",
        },
        json=provider.simulate_alert(),
    )
