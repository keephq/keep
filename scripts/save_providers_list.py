from keep.providers.providers_factory import ProviderEncoder, ProvidersFactory
import json


def save_providers_list():
    providers_list = ProvidersFactory.get_all_providers(ignore_cache_file=True)
    sorted_providers_list = sorted(providers_list, key=lambda x: x.type)
    print(f"Found {len(sorted_providers_list)} providers:")
    for i, provider in enumerate(sorted_providers_list):
        print(f"{i+1:3d}. {provider.type}")
    print("Saving to providers_list.json")
    with open("providers_list.json", "w", encoding="utf-8") as f:
        json.dump(sorted_providers_list, f, cls=ProviderEncoder, indent=4)
    print("Saved providers list to providers_list.json")


if __name__ == "__main__":
    save_providers_list()
