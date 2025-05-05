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
    print("Saving providers list as json")
    providers_list = ProvidersFactory.get_all_providers(ignore_cache_file=True)
    with open("providers_list.json", "w") as f:
        json.dump(providers_list, f, cls=ProviderEncoder, indent=4)


save_providers_list()
