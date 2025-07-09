#!/bin/bash

# Save providers list to providers_list.json
python3 ./scripts/save_providers_list.py

# Generate JSON schema from providers list
cd keep-ui && npm run build:workflow-yaml-json-schema