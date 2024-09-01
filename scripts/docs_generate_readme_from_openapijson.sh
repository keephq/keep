
#!/bin/bash

cd ../docs;

# Before running this script, make sure you have update the openapi.json from the backend & backend is in the latest state.
printf "Fetching the latest openapi.json from the backend, make sure recent backend is launched...\n"
curl http://localhost:8080/openapi.json > ./openapi.json

python3 ../scripts/docs_openapi_converter.py --source ./openapi.json --dest ./openapi.json
npx @mintlify/scraping@latest openapi-file ./openapi.json -o ./api-ref