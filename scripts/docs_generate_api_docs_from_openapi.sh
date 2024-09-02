
#!/bin/bash

cd $(dirname "$0")/../docs;

# Before running this script, make sure you have update the openapi.json from the backend & backend is in the latest state.
printf "Fetching the latest openapi.json."
curl http://localhost:8080/openapi.json > ./openapi.json

# Check if curl was successful
if [ $? -ne 0 ]; then
    echo "🔴🔴🔴 Error: Failed to download openapi.json, please run Keep backend. 🔴🔴🔴"
    exit 1
fi

echo "Successfully downloaded openapi.json"

python3 ../scripts/docs_openapi_converter.py --source ./openapi.json --dest ./openapi.json
npx @mintlify/scraping@latest openapi-file ./openapi.json -o api-ref

echo "Checking mint.json for missing files..."
./../scripts/docs_validate_navigation.sh