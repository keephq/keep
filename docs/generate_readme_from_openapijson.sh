
#!/bin/bash

# Before running this script, make sure you have update the openapi.json from the backend, (/docs route)

python3 openapi_converter.py --source ./openapi.json --dest ./openapi.json
npx @mintlify/scraping@latest openapi-file ./openapi.json -o ./api-ref