#!/bin/sh

# Verify env var and if not exit
if [ -z "$KEYCLOAK_ADMIN" ]; then
    echo "KEYCLOAK_ADMIN is not set. Exiting..."
    exit 1
fi
if [ -z "$KEYCLOAK_ADMIN_PASSWORD" ]; then
    echo "KEYCLOAK_ADMIN_PASSWORD is not set. Exiting..."
    exit 1
fi
if [ -z "$KC_HTTP_RELATIVE_PATH" ]; then
    echo "KC_HTTP_RELATIVE_PATH is not set. Exiting..."
    exit 1
fi

# If not KEEP_URL, default Keep frontend to http://localhost:3000
if [ -z "$KEEP_URL" ]; then
    echo "KEEP_URL is not set. Defaulting to http://localhost:3000"
    KEEP_URL="http://localhost:3000"
fi

# Start Keycloak in the background
echo "Starting Keycloak"
/opt/keycloak/bin/kc.sh start-dev --features=preview --import-realm -Dkeycloak.profile.feature.scripts=enabled -Dkeycloak.migration.strategy=OVERWRITE_EXISTIN &
echo "Keycloak started"
# Try to connect to Keycloak - wait until Keycloak is ready or timeout
echo "Waiting for Keycloak to be ready"
/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/${KC_HTTP_RELATIVE_PATH} --realm master --user ${KEYCLOAK_ADMIN} --password ${KEYCLOAK_ADMIN_PASSWORD}
while [ $? -ne 0 ]; do
     echo "Keycloak is not ready yet"
     sleep 5
     /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/${KC_HTTP_RELATIVE_PATH} --realm master --user ${KEYCLOAK_ADMIN} --password ${KEYCLOAK_ADMIN_PASSWORD}
done

if [ $? -eq 0 ]; then
     echo "Keycloak is ready"
else
     echo "Fail to connect to Keycloak. Exiting..."
     exit 1
fi

# Configure the theme
echo "Configuring Signin theme (for Keep tenant)"
/opt/keycloak/bin/kcadm.sh update realms/keep -s "loginTheme=keywind"
echo "Configuring Admin Console theme (for Orgs)"
/opt/keycloak/bin/kcadm.sh update realms/keep -s "adminTheme=phasetwo.v2"
/opt/keycloak/bin/kcadm.sh update realms/master -s "adminTheme=phasetwo.v2"
echo "Themes configured"

# Configure the event listener provider
echo "Configuring event listener provider"
/opt/keycloak/bin/kcadm.sh update realms/keep -s "eventsListeners+=last_login"
echo "Event listener 'last_login' configured"

# Configure Content-Security-Policy and X-Frame-Options
# So that the SSO connect works with the Keep UI
echo "Configuring Content-Security-Policy and X-Frame-Options"
/opt/keycloak/bin/kcadm.sh update realms/keep -s 'browserSecurityHeaders.contentSecurityPolicy="frame-src '\''self'\'' '"$KEEP_URL"'; frame-ancestors '\''self'\'' '"$KEEP_URL"'; object-src '\''none'\'';"'
/opt/keycloak/bin/kcadm.sh update realms/keep -s 'browserSecurityHeaders.xFrameOptions="ALLOW"'
echo "Content-Security-Policy and X-Frame-Options configured"

# just to keep the container running
tail -f /dev/null

# command to run this container with mount to this directory:
# docker run -v $(pwd):/mnt -it --entrypoint /bin/sh quay.io/keycloak/keycloak:latest
