


docker run --name phasetwo_test --rm -p 8181:8080 \
    -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
    quay.io/phasetwo/phasetwo-keycloak:latest \
    start-dev


http://localhost:8181/realms/keep/portal/
http://localhost:8181/realms/keep/portal/

https://euc1.auth.ac/auth/realms/keep/portal


# delete realm to refresh
1. delete the realm from the UI
2. restart

# how to use phasetwo plugins


# what to read:
1. main repo - https://github.com/p2-inc/keycloak-orgs
2. SSO wizzards -
3.



# New Tutorial

## Keycloak configuration
### https://github.com/p2-inc/keycloak-orgs
1. Change admin theme so that "Org" will show
2. Create organization
3. Add all members to organization
    TODO: how to do it automatically?

4. For iframe -
   1. http://localhost:8181/auth/admin/master/console/#/keep/realm-settings/security-defenses
   2. frame-src 'self' http://localhost:3000; frame-ancestors 'self' http://localhost:3000; object-src 'none';


## LDAP
1. openldap container - the ldap server
2. ldap-ui - ui for the ldap
3. load ldap.ldif


http://localhost:8181/auth/admin/master/console/#/keep


## Sign in page
# 1. build: pnpm build:jar
