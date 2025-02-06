#!/bin/sh
echo "Starting Nextjs [${API_URL}]"
echo "AUTH_TYPE: ${AUTH_TYPE}"
sh ./scripts/check-required-env-vars.sh
exec node server.js
