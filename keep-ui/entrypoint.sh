#!/bin/sh

if [ -n "$NEXT_PUBLIC_API_URL" ]; then
  echo "Patching NEXT_PUBLIC_API_URL - ${NEXT_PUBLIC_API_URL}"
  # In case it's deployed on Kubernetes using the helm chart, we need to replace the NEXT_PUBLIC_API_URL
  find /app/.next \( -type d -name .git -prune \) -o -type f -print0 | xargs -0 sed -i "s#APP_NEXT_PUBLIC_API_URL-keep-api#$NEXT_PUBLIC_API_URL#g"
fi

echo "Starting Nextjs"
exec node server.js
