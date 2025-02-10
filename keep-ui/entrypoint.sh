#!/bin/sh
echo "Starting Nextjs [${API_URL}]"
echo "AUTH_TYPE: ${AUTH_TYPE}"
if [ -n "${NEXTAUTH_SECRET}" ]; 
then echo "NEXTAUTH_SECRET is set"; 
else echo "‼️ WARNING: NEXTAUTH_SECRET is not set"; fi
exec node server.js
