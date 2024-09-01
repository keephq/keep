#!/bin/bash

OPENAPI_JSON="$(dirname "$0")/../docs/openapi.json"
OPENAPI_JSON_BACKUP="$(dirname "$0")/../docs/openapi_backup.json"

# Download the latest openapi.json
curl http://localhost:8080/openapi.json > $OPENAPI_JSON_BACKUP

# Compare the 'paths' key of both JSON files directly
if cmp -s <(jq '.paths' "$OPENAPI_JSON") <(jq '.paths' "$OPENAPI_JSON_BACKUP"); then
    echo "API docs are up-to-date."
else
    echo "🔴🔴🔴 API docs are not up-to-date. 🔴🔴🔴"
    echo "The 'paths' sections in openapi.json is not up-to-date with http://localhost:8080/openapi.json."
    echo "Most probably it means that the API was updated, and the API docs should be regenerated."
    echo "Please run the following command to regenerate the API docs: ./scripts/docs_generate_api_docs_from_openapi.sh"
    exit 1
fi

rm $OPENAPI_JSON_BACKUP