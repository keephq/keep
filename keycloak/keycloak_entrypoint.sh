#!/bin/sh

# Start Keycloak in the background
echo "Starting Keycloak"
/opt/keycloak/bin/kc.sh start-dev --import-realm -Dkeycloak.migration.strategy=OVERWRITE_EXISTIN &
echo "Keycloak started"
# Try to connect to Keycloak - wait until Keycloak is ready or timeout
echo "Waiting for Keycloak to be ready"
/opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user keep_kc --password keep_kc
while [ $? -ne 0 ]; do
     echo "Keycloak is not ready yet"
     sleep 5
     /opt/keycloak/bin/kcadm.sh config credentials --server http://localhost:8080/auth --realm master --user keep_kc --password keep_kc
done

if [ $? -eq 0 ]; then
     echo "Keycloak is ready"
else
     echo "Fail to connect to Keycloak. Exiting..."
     exit 1
fi

# Configure the theme
echo "Configuring theme"
/opt/keycloak/bin/kcadm.sh update realms/keep -s "loginTheme=keywind"
/opt/keycloak/bin/kcadm.sh update realms/keep -s "loginTheme=phasetwo.v2"
echo "Theme configured"

# Export the realm
echo "Exporting realm"
/opt/keycloak/bin/kcadm.sh get realms/keep -o /tmp/realm-export.json
echo "Realm exported"

# just to keep the container running
tail -f /dev/null

# command to run this container with mount to this directory:
# docker run -v $(pwd):/mnt -it --entrypoint /bin/sh quay.io/keycloak/keycloak:latest
