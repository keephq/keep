#!/bin/sh

echo "Starting Nextjs [${API_URL}]"
echo "AUTH_TYPE: ${AUTH_TYPE}"

if [ -n "${NEXTAUTH_SECRET}" ]; then
    echo "NEXTAUTH_SECRET is set"
else
    echo "‼️ WARNING: NEXTAUTH_SECRET is not set"
fi

# Check Azure AD environment variables if AUTH_TYPE is "azuread"
if [ "${AUTH_TYPE}" = "azuread" ]; then
    echo "Checking Azure AD configuration..."

    for var in KEEP_AZUREAD_CLIENT_ID KEEP_AZUREAD_CLIENT_SECRET KEEP_AZUREAD_TENANT_ID; do
        if [ -n "${!var}" ]; then
            # Print first 6 characters followed by XXXX
            value="${!var}"
            masked="${value:0:6}XXXX"
            echo "✓ ${var}: ${masked}"
        else
            echo "⚠️ WARNING: ${var} is not set"
        fi
    done
fi

exec node server.js
