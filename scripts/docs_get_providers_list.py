"""
To execute the script and copy to clipboard:
`
cd scripts
python docs_get_providers_list.py | pbcopy
python docs_get_providers_list.py --validate # To check docs/providers/overview.mdx and if all providers are documented.
"""

import argparse
import glob
import os
import re
import sys

LOGO_DEV_PUBLISHABLE_KEY = "pk_dfXfZBoKQMGDTIgqu7LvYg"

NON_DOCUMENTED_PROVIDERS = [
]


def validate_overview_is_complete(documented_providers):
    """
    This function validates the providers to be added to the overview.md file.
    """
    overview_file = "./../docs/providers/overview.mdx"
    with open(overview_file, "r") as file:
        overview_content = file.read()

        for provider in documented_providers:
            if provider not in overview_content:
                print(
                    f"""Provider {provider} is not in the docs/providers/overview.md file,
use scripts/docs_get_providers_list.py to generate recent providers list and update the file."""
                )
                exit(1)


def validate_all_providers_are_documented(documented_providers):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, parent_dir)

    documented_providers = [provider.lower() for provider in documented_providers]
    from keep.providers.providers_factory import ProvidersFactory

    for provider in ProvidersFactory.get_all_providers():
        provider_name = provider.display_name.lower()
        if (
            provider_name not in documented_providers
            and provider_name not in NON_DOCUMENTED_PROVIDERS
            and not provider.coming_soon
        ):
            raise Exception(
                f"""Provider "{provider_name}" is not documented in the docs/providers/documentation folder,
please document it and run the scripts/docs_get_providers_list.py --validate script again.

Provider's PROVIDER_DISPLAY_NAME should match the title in the documentation file: {{PROVIDER_DISPLAY_NAME}}-provider.mdx.

{provider_name}-provider.mdx not found.

Documented providers: {documented_providers}
Excluded list: {NON_DOCUMENTED_PROVIDERS}"""
            )


def main():
    """
    This script lists all the integrations in the documentation folder and outputs a markdown list of links.
    Post here to get clickable links: https://markdownlivepreview.com/
    """

    files = glob.glob(os.path.join("./../docs/providers/documentation/", "*"))

    files_to_docs_urls = {}

    for file_path in files:
        if os.path.isfile(file_path):
            with open(file_path, "r") as file:
                for line in file.readlines():
                    match = re.search(r"title:\s*[\"|\']([^\"]+)[\"|\']", line)
                    if match:
                        url = "/providers/documentation/" + file_path.replace(
                            "./../docs/providers/documentation/", ""
                        ).replace(".mdx", "")
                        provider_name = match.group(1).replace("Provider", "").strip()

                        # Due to https://github.com/keephq/keep/pull/1239#discussion_r1643196800
                        if "Slack" in provider_name:
                            provider_name = "Slack"

                        if provider_name not in ["Mock"]:
                            files_to_docs_urls[provider_name] = url
                        break

    # Sort by alphabetical order
    files_to_docs_urls = {
        k: v for k, v in sorted(files_to_docs_urls.items(), key=lambda item: item[1])
    }

    mintlify_cards = "<CardGroup cols={3}>\n"
    documented_providers = []
    for provider_name, url in files_to_docs_urls.items():
        # For logo dev we need to remove spaces and get the first part of the name
        # e.g., grafana-on-call -> grafana
        provider_name_logo_dev: str = provider_name.split(" ")[0].lower()

        # Special cases
        if provider_name_logo_dev == "datadog":
            provider_name_logo_dev = "datadoghq"
        if provider_name_logo_dev == "gcp":
            provider_name_logo_dev = "googlecloudpresscorner"
        if provider_name_logo_dev == "elastic":
            provider_name_logo_dev = "elastic.co"
        if provider_name_logo_dev == "sentry":
            provider_name_logo_dev = "sentry.io"
        if provider_name_logo_dev == "kubernetes":
            provider_name_logo_dev = "kubernetes.io"

        # logo.dev requires .com
        if (
            provider_name_logo_dev.endswith(".co") is False
            and provider_name_logo_dev.endswith(".io") is False
        ):
            provider_name_logo_dev += ".com"
        svg_icon = f'<img src="https://img.logo.dev/{provider_name_logo_dev}?token={LOGO_DEV_PUBLISHABLE_KEY}" />'
        if svg_icon:
            new_card = f"""
<Card
  title="{provider_name}"
  href="{url}"
  icon={{ {svg_icon} }}
></Card>
"""
            mintlify_cards += new_card
            documented_providers.append(provider_name)
    mintlify_cards += "</CardGroup>"

    # Checking --validate flag
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    # If --validate flag is set, print the list of providers to validate
    if args.validate:
        validate_all_providers_are_documented(documented_providers)
        validate_overview_is_complete(documented_providers)
    else:
        print(mintlify_cards)


if __name__ == "__main__":
    main()
