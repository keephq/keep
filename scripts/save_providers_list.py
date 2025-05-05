from dataclasses import _MISSING_TYPE
import json
from keep.providers.models.provider_config import ProviderScope
from keep.providers.providers_factory import ProvidersFactory


class ProviderEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ProviderScope):
            dct = o.__dict__
            dct.pop("__pydantic_initialised__", None)
            return dct
        elif isinstance(o, _MISSING_TYPE):
            return None
        return o.dict()


def save_providers_list():
    providers_list = ProvidersFactory.get_all_providers(ignore_cache_file=True)
    sorted_providers_list = sorted(providers_list, key=lambda x: x.type)
    print(f"Found {len(sorted_providers_list)} providers:")
    for i, provider in enumerate(sorted_providers_list):
        print(f"{i+1:3d}. {provider.type}")
    print("Saving to providers_list.json")
    with open("providers_list.json", "w") as f:
        json.dump(sorted_providers_list, f, cls=ProviderEncoder, indent=4)
    print("Saved providers list to providers_list.json")


save_providers_list()
