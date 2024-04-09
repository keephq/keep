#!/bin/sh

# Then run the build
echo "Env vars:"
env
echo "Building"
unset NODE_ENV
unset __NEXT_PRIVATE_STANDALONE_CONFIG
unset AUTH0_MANAGEMENT_DOMAIN
unset AUTH0_CLIENT_ID
unset AUTH0_CLIENT_SECRET
next dev -p 3000
