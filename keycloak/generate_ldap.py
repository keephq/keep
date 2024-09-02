BASE_DN = "dc=keep,dc=com"
FILE_NAME = "ldap_generated.ldif"

# Predefined users data
predefined_users = [
    {
        "uid": "john.doe",
        "sn": "Doe",
        "givenName": "John",
        "cn": "John Doe",
        "mail": "john.doe@keep.com",
        "team": "teamA",
    },
    {
        "uid": "jane.smith",
        "sn": "Smith",
        "givenName": "Jane",
        "cn": "Jane Smith",
        "mail": "jane.smith@keep.com",
        "team": "teamB",
    },
    {
        "uid": "alice.johnson",
        "sn": "Johnson",
        "givenName": "Alice",
        "cn": "Alice Johnson",
        "mail": "alice.johnson@keep.com",
        "team": "teamA",
    },
]

# Teams
teams = [
    "teamA",
    "teamB",
    "teamC",
    "teamD",
    "teamE",
    "teamF",
    "teamG",
    "teamH",
    "teamI",
    "teamJ",
]

# Initialize team members dictionary
team_members = {team: [f"cn=admin,{BASE_DN}"] for team in teams}


def generate_ldif():
    with open(FILE_NAME, "w") as f:
        # Root entry for the domain
        f.write(
            f"""# Root entry for the domain
dn: {BASE_DN}
objectClass: top
objectClass: dcObject
objectClass: organization
o: Keep Organization
dc: keep

# Administrator user
dn: cn=admin,{BASE_DN}
objectClass: simpleSecurityObject
objectClass: organizationalRole
cn: admin
userPassword: admin_password
description: LDAP administrator

# Groups
dn: ou=groups,{BASE_DN}
objectClass: top
objectClass: organizationalUnit
ou: groups

"""
        )

        # Add organizational unit for users
        f.write(
            f"""# Users
dn: ou=users,{BASE_DN}
objectClass: top
objectClass: organizationalUnit
ou: users

"""
        )

        # Add predefined users
        for user in predefined_users:
            user_dn = f"uid={user['uid']},ou=users,{BASE_DN}"
            team_members[user["team"]].append(user_dn)
            f.write(
                f"""dn: {user_dn}
objectClass: inetOrgPerson
uid: {user['uid']}
sn: {user['sn']}
givenName: {user['givenName']}
cn: {user['cn']}
displayName: {user['cn']}
userPassword: password123
mail: {user['mail']}
o: Keep Organization
employeeType: Developer
memberOf: cn={user['team']},ou=groups,{BASE_DN}

"""
            )

        # Generate additional users
        for i in range(4, 101):
            uid = f"user{i:03d}"
            sn = f"LastName{i}"
            givenName = f"User{i}"
            cn = f"User{i} LastName{i}"
            displayName = f"User{i} LastName{i}"
            mail = f"user{i}@keep.com"
            team = teams[(i - 1) % 10]
            user_dn = f"uid={uid},ou=users,{BASE_DN}"
            team_members[team].append(user_dn)
            f.write(
                f"""dn: {user_dn}
objectClass: inetOrgPerson
uid: {uid}
sn: {sn}
givenName: {givenName}
cn: {cn}
displayName: {displayName}
userPassword: password123
mail: {mail}
o: Keep Organization
employeeType: Developer
memberOf: cn={team},ou=groups,{BASE_DN}

"""
            )

        # Append uniqueMember entries directly to each group
        for team in teams:
            f.write(
                f"""dn: cn={team},ou=groups,{BASE_DN}
objectClass: top
objectClass: groupOfUniqueNames
cn: {team}
"""
            )
            for member_dn in team_members[team]:
                f.write(f"uniqueMember: {member_dn}\n")
            f.write("\n")


if __name__ == "__main__":
    generate_ldif()
    print(f"LDAP LDIF file has been generated: {FILE_NAME}")
