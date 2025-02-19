#!/bin/sh

echo "Starting Nextjs [${API_URL}]"
echo "AUTH_TYPE: ${AUTH_TYPE}"

if [ -n "${NEXTAUTH_SECRET}" ]; then
    echo "NEXTAUTH_SECRET is set"
else
    echo "‼️ WARNING: NEXTAUTH_SECRET is not set"
fi

# Check Azure AD environment variables if AUTH_TYPE is "azuread"
if [ "${AUTH_TYPE}" = "azuread" ] || [ "${AUTH_TYPE}" = "AZUREAD" ]; then
    echo "Checking Azure AD configuration..."

    # Simple direct checks with first 4 chars display
    if [ -n "$KEEP_AZUREAD_CLIENT_ID" ]; then
        echo "✓ KEEP_AZUREAD_CLIENT_ID: $(printf "%.4s" "$KEEP_AZUREAD_CLIENT_ID")****"
    else
        echo "⚠️ WARNING: KEEP_AZUREAD_CLIENT_ID is not set"
    fi

    if [ -n "$KEEP_AZUREAD_CLIENT_SECRET" ]; then
        echo "✓ KEEP_AZUREAD_CLIENT_SECRET: $(printf "%.4s" "$KEEP_AZUREAD_CLIENT_SECRET")****"
    else
        echo "⚠️ WARNING: KEEP_AZUREAD_CLIENT_SECRET is not set"
    fi

    if [ -n "$KEEP_AZUREAD_TENANT_ID" ]; then
        echo "✓ KEEP_AZUREAD_TENANT_ID: $(printf "%.4s" "$KEEP_AZUREAD_TENANT_ID")****"
    else
        echo "⚠️ WARNING: KEEP_AZUREAD_TENANT_ID is not set"
    fi
fi

exec node server.js
