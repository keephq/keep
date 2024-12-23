#!/bin/bash

cd "$(dirname "$0")/../docs"

# Define the JSON file
MINT_JSON="mint.json"

# Define the exclusion lists
EXCLUDE_LIST=("node_modules")
EXCLUDE_FILE_LIST=(
    "./applications/github.mdx"
    "api-ref/root"
)

# Check if mint.json exists
if [[ ! -f "$MINT_JSON" ]]; then
    echo "mint.json file not found!"
    exit 1
fi

# Function to check if a path is in the exclusion list
is_excluded() {
    local file_path=$1

    # Check if the file path is in the directory exclusion list
    for exclude in "${EXCLUDE_LIST[@]}"; do
        if [[ $file_path == *"$exclude"* ]]; then
            return 0 # The file is in an excluded directory path
        fi
    done

    # Check if the exact file is in the file exclusion list
    for exclude_file in "${EXCLUDE_FILE_LIST[@]}"; do
        if [[ $file_path == "$exclude_file" ]]; then
            return 0 # The file is in the exclusion file list
        fi
    done

    return 1 # The file is not excluded
}

echo "Checking for missing files in mint.json..."

is_missing=0

# Go over each .mdx file in all subdirectories within the current directory
while IFS= read -r -d '' file; do
    # Check if the file is in the exclusion list
    if is_excluded "$file"; then
        continue
    fi

    # Get the relative path without the leading "./" and without the file extension
    relative_path="${file#./}"
    relative_path="${relative_path%.mdx}"

    # Check if the relative path is listed in mint.json
    if grep -q "\"$relative_path\"" "$MINT_JSON"; then
        # echo "File $relative_path is listed in mint.json"
        :
    else
        echo "\"$relative_path\","
        is_missing=1
    fi
done < <(find . -mindepth 2 -type f -name "*.mdx" -print0 | sort -z)

if [[ $is_missing -ne 0 ]]; then
    echo "🔴🔴🔴 👆 those files are missing in docs/mint.json. That's a file responsible for rendering docs navigation."
    echo "Please add the new docs page there or to the EXCLUDE_FILE_LIST of the current script."
    echo "Otherwise the page will be really hard to navigate to :)"
    echo "Run ./scripts/docs_validate_navigation.sh to check if the issue is fixed."
    exit 1 # Exit with an error code to fail the CI/CD process
fi
