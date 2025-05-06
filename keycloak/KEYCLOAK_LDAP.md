- UI display name: keep-ldap
- Vendor: Active Directory
- Connection URL: ldap://openldap:389
- Bind Type: simple
- Bind DN: cn=admin,dc=keep,dc=com
- Bind credentials: admin_password
- Edit mode: READ_ONLY
- Users DN: ou=users,dc=keep,dc=com
- Username LDAP attribute: uid
- RDN LDAP attribute: uid
- UUID LDAP attribute: entryUUID
- User object classes: inetOrgPerson

## Mappers

- groups
  - LDAP Groups DN: ou=groups,dc=keep,dc=com
  - Group Name LDAP Attribute: cn
  - Group Object Classes: groupOfUniqueNames
  - Membership LDAP Attribute: uniqueMember
  - Membership Attribute Type: DN
  - Membership User LDAP Attribute: uid
  - Mode: READ_ONLY
  - User Groups Retrieve Strategy: GET_GROUPS_FROM_USER_MEMBEROF_ATTRIBUTE
  - Member-Of LDAP Attribute: memberOf

# How to load LDAP

```
ldapadd -c -x -D "cn=admin,dc=keep,dc=com" -w admin_password -f ./ldif/ldap_orgs.ldif -H ldap://localhost:389
```

# Create the LDAP in Keycloak

/opt/keycloak/bin/kcadm.sh create components -r keep \
 --set name=keep-ldap \
 --set providerId=ldap \
 --set providerType=org.keycloak.storage.UserStorageProvider \
 --set parentId=keep \
 --set 'config.vendor=["ad"]' \
 --set 'config.connectionUrl=["ldap://openldap:389"]' \
 --set 'config.authType=["simple"]' \
 --set 'config.bindDn=["cn=admin,dc=keep,dc=com"]' \
 --set 'config.bindCredential=["admin_password"]' \
 --set 'config.editMode=["READ_ONLY"]' \
 --set 'config.usersDn=["ou=users,dc=keep,dc=com"]' \
 --set 'config.usernameLDAPAttribute=["uid"]' \
 --set 'config.rdnLDAPAttribute=["uid"]' \
 --set 'config.uuidLDAPAttribute=["entryUUID"]' \
 --set 'config.userObjectClasses=["inetOrgPerson"]' \
 --set 'config.searchScope=[1]' \
 --set 'config.enabled=[true]' \
 --set 'config.priority=[0]'

#

LDAP_ID=$(/opt/keycloak/bin/kcadm.sh get components -r keep --query name=keep-ldap | grep -oP '"id" : "\K[^"]+')
echo "LDAP Provider ID: $LDAP_ID"

# Create the group mapper

### Important: Replace parentId with LDAP_ID!!!

/opt/keycloak/bin/kcadm.sh create components -r keep -f jsons/group-mapper.json

# Create the group token claim

### get the id

/opt/keycloak/bin/kcadm.sh get client-scopes -r keep --query name=profile

### e.g. 7e6b5d45-2372-4a49-a11e-6bdf5de0d7f1

/opt/keycloak/bin/kcadm.sh create client-scopes/6edf977d-6aac-4073-988f-4c14d2dfaff3/protocol-mappers/models -r keep -f jsons/group-claim.json

#

/opt/keycloak/bin/kcadm.sh create client-scopes/6edf977d-6aac-4073-988f-4c14d2dfaff3/protocol-mappers/models -r keep -f jsons/tenant-ids-js-mapper.json
