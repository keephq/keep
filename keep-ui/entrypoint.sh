#!/bin/sh

if [ -n "$API_URL" ]; then
  echo "Patching API_URL - ${API_URL}"
  # In case it's deployed on Kubernetes using the helm chart, we need to replace the NEXT_PUBLIC_API_URL
  find /app/.next \( -type d -name .git -prune \) -o -type f -print0 | xargs -0 sed -i "s#http://APP_API_URL-keep-api#$API_URL#g"
fi

echo "Starting Nextjs"
exec node server.js
