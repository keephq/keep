#!/bin/sh

# This allows us to dynamically set the API_URL based on the branch name
# This is useful for testing PRs on Vercel
if [ -n "$VERCEL_GIT_COMMIT_REF" ]; then
    branch_name_sanitized=$(echo $VERCEL_GIT_COMMIT_REF | sed 's/\//-/g' | cut -c 1-63)
    # Here we replace 'keep-api' in the URL with 'keep-api-{sanitizedBranchName}' if the branch is not main
    if [ "$branch_name_sanitized" != "main" ]; then
        service_name="keep-api-${branch_name_sanitized}"

        # Ensure the service_name is no longer than 63 characters
        if [ ${#service_name} -gt 63 ]; then
            # 49 because this is the max length of the URL in cloud run
            service_name=$(echo "$service_name" | cut -c 1-49)
        fi

        # Check if the last character of service_name is a hyphen ("-")
        if [ "${service_name: -1}" = "-" ]; then
            service_name="${service_name::-1}" # Remove the last character
        fi
        echo "Patch API_URL to use service name: ${service_name}"
        export API_URL=$(echo $API_URL | sed "s|keep-api|${service_name}|")
        echo "API_URL: ${API_URL}"
    fi
fi

echo "Starting Nextjs [${API_URL}]"
echo "Env vars:"
env
exec node server.js
