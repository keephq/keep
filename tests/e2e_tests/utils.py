from keep.providers.providers_factory import ProvidersFactory
import requests


def trigger_alert(provider_name):
    provider = ProvidersFactory.get_provider_class(provider_name)
    requests.post(
        f"https://8080-35c4n0r-keep-j5ok1nvq1vv.ws-us117.gitpod.io/alerts/event/{provider_name}",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": "3db87031-41c7-43cf-9a20-7cdbcf32f97d",
        },
        json=provider.simulate_alert(),
    )
