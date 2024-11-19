#!/bin/sh
echo "Starting Nextjs [${API_URL}]"

# force Keep to respect the proxy environment variables
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ] || [ -n "$http_proxy" ] || [ -n "$https_proxy" ]; then
    echo "Proxy environment variables detected, running with patch"
    # Run with patch
    exec node -r ./proxy-patch.js server.js
else
    exec node server.js
fi
