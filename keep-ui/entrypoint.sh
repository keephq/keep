#!/bin/sh

echo "Check that we have NEXT_PUBLIC_API_URL vars"
test -n "$NEXT_PUBLIC_API_URL"

find /app/.next \( -type d -name .git -prune \) -o -type f -print0 | xargs -0 sed -i "s#APP_NEXT_PUBLIC_API_URL-keep-api#$NEXT_PUBLIC_API_URL#g"

echo "Starting Nextjs"
exec "node server.js"
