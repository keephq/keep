#!/bin/bash

if [ -n "$VERCEL_GIT_COMMIT_REF" ]; then
    branch_name_sanitized=$(echo $VERCEL_GIT_COMMIT_REF | sed 's/\//-/g' | cut -c 1-63)
    # Here we replace 'keep-api' in the URL with 'keep-api-{sanitizedBranchName}'
    export NEXT_PUBLIC_API_URL=$(echo $NEXT_PUBLIC_API_URL | sed "s|keep-api|keep-api-${branch_name_sanitized}|")
    export API_URL=$(echo $API_URL | sed "s|keep-api|keep-api-${branch_name_sanitized}|")
fi

# Then run the build
next build
