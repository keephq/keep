#!/bin/sh
echo "Starting Nextjs [${API_URL}]"
echo "Env vars:"
env
exec node server.js
