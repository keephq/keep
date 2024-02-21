


docker run --name phasetwo_test --rm -p 8181:8080 \
    -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
    quay.io/phasetwo/phasetwo-keycloak:latest \
    start-dev


http://localhost:8181/realms/keep/portal/
http://localhost:8181/realms/keep/portal/

https://euc1.auth.ac/auth/realms/keep/portal
