import os
import re
import glob


def main():
    """
    This script lists all the integrations in the documentation folder and outputs a markdown list of links.
    Post here to get clickable links: https://markdownlivepreview.com/
    """

    files = glob.glob(os.path.join("./../docs/providers/documentation/", '*'))

    files_to_docs_urls = {}
    
    for file_path in files:
        if os.path.isfile(file_path):
            with open(file_path, 'r') as file:
                for line in file.readlines():
                    match = re.search(r'title:\s*"([^"]+)"', line)
                    if match:
                        url = "https://docs.keephq.dev/providers/documentation/" + \
                            file_path.replace('./../docs/providers/documentation/', '').\
                            replace('.mdx', '')
                        provider_name = match.group(1).replace('Provider', '').strip()

                        if provider_name not in ["Mock"]:
                            files_to_docs_urls[provider_name] = url
                        break

    # Sort by alphabetical order
    files_to_docs_urls = {k: v for k, v in sorted(files_to_docs_urls.items(), key=lambda item: item[1])}
    print(", ".join(f"[{k}]({v})" for k, v in files_to_docs_urls.items()))


if __name__ == "__main__":
    main()
