#!/bin/sh

# This allows us to dynamically set the API_URL and NEXT_PUBLIC_API_URL based on the branch name
# This is useful for testing PRs on Vercel
if [ -n "$VERCEL_GIT_COMMIT_REF" ]; then
    branch_name_sanitized=$(echo $VERCEL_GIT_COMMIT_REF | sed 's/\//-/g' | cut -c 1-63)
    # Here we replace 'keep-api' in the URL with 'keep-api-{sanitizedBranchName}' if the branch is not main
    if [ "$branch_name_sanitized" != "main" ]; then
        service_name="keep-api-${branch_name_sanitized}"

        # Ensure the service_name is no longer than 63 characters
        if [ ${#service_name} -gt 63 ]; then
            service_name=$(echo "$service_name" | cut -c 1-63)
        fi

        # Check if the last character of service_name is a hyphen ("-")
        if [ "${service_name: -1}" = "-" ]; then
            service_name="${service_name::-1}" # Remove the last character
        fi

        export NEXT_PUBLIC_API_URL=$(echo $NEXT_PUBLIC_API_URL | sed "s|keep-api|${service_name}|")
        export API_URL=$(echo $API_URL | sed "s|keep-api|${service_name}|")
    fi
fi

# Then run the build
echo "Env vars:"
env
echo "Building"
next build
