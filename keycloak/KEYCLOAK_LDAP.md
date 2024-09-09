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
