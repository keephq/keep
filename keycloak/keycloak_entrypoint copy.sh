#!/bin/bash

KEYCLOAK_URL="http://localhost:8181"
KEYCLOAK_ADMIN=keep_kc
KEYCLOAK_PASSWORD=keep_kc

echo "Obtaining admin token"

ADMIN_TOKEN=$(curl -X POST "${KEYCLOAK_URL}/auth/realms/keep/protocol/openid-connect/token" \
   -H "Content-Type: application/x-www-form-urlencoded" \
   -d "username=${KEYCLOAK_ADMIN}" \
   -d "password=${KEYCLOAK_PASSWORD}" \
   -d "grant_type=password" \
   -d "client_id=admin-cli" | jq -r '.access_token')
