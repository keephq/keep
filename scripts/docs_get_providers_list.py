"""
To execute the script and copy to clipboard:
`
cd scripts
python get_providers_list.py | pbcopy
python get_providers_list.py --validate # To check docs/providers/overview.mdx
"""

import argparse
import glob
import os
import re

LOGO_DEV_PUBLISHABLE_KEY = "pk_dfXfZBoKQMGDTIgqu7LvYg"


def validate(providers_to_validate):
    """
    This function validates the providers to be added to the overview.md file.
    """
    overview_file = "./../docs/providers/overview.mdx"
    with open(overview_file, "r") as file:
        overview_content = file.read()

        for provider in providers_to_validate:
            if provider not in overview_content:
                print(
                    f"""Provider {provider} is not in the docs/providers/overview.md file,
use scripts/get_providers_list.py to generate recent providers list and update the file."""
                )
                exit(1)


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
    providers_to_validate = []
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
            providers_to_validate.append(provider_name)
    mintlify_cards += "</CardGroup>"

    # Checking --validate flag
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()

    # If --validate flag is set, print the list of providers to validate
    if args.validate:
        validate(providers_to_validate=providers_to_validate)
    else:
        print(mintlify_cards)


if __name__ == "__main__":
    main()
