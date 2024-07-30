import {
  Title,
  Subtitle,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Button,
  MultiSelect,
  MultiSelectItem,
  Badge
} from "@tremor/react";
import Loading from "app/loading";
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import Image from "next/image";
import { User } from "../models";
import UsersMenu from "./users-menu";
import { User as AuthUser } from "next-auth";
import { UserPlusIcon } from "@heroicons/react/24/outline";
import { useState, useEffect } from "react";
import AddUserModal from "./add-user-modal";
import { AuthenticationType } from "utils/authenticationType";
import { useUsers } from "utils/hooks/useUsers";
import { useRoles } from "utils/hooks/useRoles";
import { useGroups } from "utils/hooks/useGroups";
import { useConfig } from "utils/hooks/useConfig";

interface Props {
  accessToken: string;
  currentUser?: AuthUser;
  selectedTab: string;
}
export interface Config {
  AUTH_TYPE: string;
}

export default function UsersSettings({
  accessToken,
  currentUser,
  selectedTab,
}: Props) {
  const apiUrl = getApiURL();
  const { data: users, isLoading, error, mutate: mutateUsers} = useUsers();
  const { data: roles } = useRoles();
  const { data: groups } = useGroups();

  const { data: configData } = useConfig();

  const [isAddUserModalOpen, setAddUserModalOpen] = useState(false);
  const [addUserError, setAddUserError] = useState("");
  const [userStates, setUserStates] = useState<{ [key: string]: { roles: string[], groups: string[] } }>({});
  const [hasChanges, setHasChanges] = useState(false);

  // Determine runtime configuration
  const authType = configData?.AUTH_TYPE as AuthenticationType;
  // The add user disabled if authType is none
  const addUserEnabled = authType !== AuthenticationType.NO_AUTH;

  useEffect(() => {
    if (users) {
      const initialUserStates = users.reduce((acc, user) => {
        acc[user.email] = {
          roles: [user.role],
          groups: user.groups? user.groups.map(group => group.name) : []
        };
        return acc;
      }, {} as { [key: string]: { roles: string[], groups: string[] } });
      setUserStates(initialUserStates);
    }
  }, [users]);

  if (!users || isLoading || !roles || !groups) return <Loading />;

  const handleRoleChange = (userId: string, newRoles: string[]) => {
    setUserStates(prevStates => ({
      ...prevStates,
      [userId]: {
        ...prevStates[userId],
        roles: newRoles
      }
    }));
    setHasChanges(true);
  };

  const handleGroupChange = (userId: string, newGroups: string[]) => {
    setUserStates(prevStates => ({
      ...prevStates,
      [userId]: {
        ...prevStates[userId],
        groups: newGroups
      }
    }));
    setHasChanges(true);
  };

  const updateUsers = async () => {
    // Implement the logic to update user roles and groups
    // This might involve calling an API endpoint
    console.log('Updating user states:', userStates);
    // After successful update, you might want to refresh the users data
    await mutateUsers();
    setHasChanges(false);
  };

  return (
    <div className="mt-10 h-full flex flex-col">
      <div className="flex justify-between mb-4">
        <div className="flex flex-col">
          <Title>Users Management</Title>
          <Subtitle>Add or remove users from your tenant</Subtitle>
          {addUserError && (
            <div className="text-red-500 text-center mt-2">{addUserError}</div> // Display error message
          )}
        </div>
        <div className="flex space-x-2">
          <Button
            color="orange"
            size="md"
            icon={UserPlusIcon}
            onClick={() => setAddUserModalOpen(true)}
            disabled={!addUserEnabled}
            tooltip={
              !addUserEnabled
                ? "Add user is disabled because Keep is running in NO_AUTH mode."
                : "Add user"
            }
          >
            Add User
          </Button>
          <Button
            color="orange"
            variant="secondary"
            size="md"
            onClick={updateUsers}
            disabled={!hasChanges}
          >
            Update Users
          </Button>
        </div>
      </div>
      <Card className="flex-grow overflow-auto h-full">
        <div className="h-full w-full overflow-auto">
          <Table className="h-full">
            <TableHead>
              <TableRow>
                <TableHeaderCell className="w-12">{/** Image */}</TableHeaderCell>
                <TableHeaderCell className="w-64">
                  {authType == AuthenticationType.MULTI_TENANT || authType == AuthenticationType.KEYCLOAK
                    ? "Email"
                    : "Username"}
                </TableHeaderCell>
                <TableHeaderCell className="w-48">Name</TableHeaderCell>
                <TableHeaderCell className="w-48 text-right">Role</TableHeaderCell>
                <TableHeaderCell className="w-48 text-right">Groups</TableHeaderCell>
                <TableHeaderCell className="w-48 text-right">
                  Created At
                </TableHeaderCell>
                <TableHeaderCell className="w-48 text-right">
                  Last Login
                </TableHeaderCell>
                <TableHeaderCell className="w-12">{/**Menu */}</TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {users.map((user) => (
                <TableRow
                  key={user.email}
                  className={`${
                    user.email === currentUser?.email ? "bg-orange-50" : null
                  }`}
                >
                  <TableCell>
                    {user.picture && (
                      <Image
                        src={user.picture}
                        alt="user picture"
                        className="rounded-full"
                        width={24}
                        height={24}
                      />
                    )}
                  </TableCell>
                  <TableCell className="w-64">
                    <div className="flex items-center justify-between">
                      <Text className="truncate">{user.email}</Text>
                      <div className="ml-2">
                        {user.ldap && (
                          <Badge color="orange">LDAP</Badge>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Text>{user.name}</Text>
                  </TableCell>
                  <TableCell className="text-right">
                    <MultiSelect
                      value={userStates[user.email]?.roles || []}
                      onValueChange={(value) => handleRoleChange(user.email, value)}
                    >
                      {roles.map((role) => (
                        <MultiSelectItem key={role.id} value={role.name}>
                          {role.name}
                        </MultiSelectItem>
                      ))}
                    </MultiSelect>
                  </TableCell>
                  <TableCell className="text-right">
                    <MultiSelect
                      value={userStates[user.email]?.groups || []}
                      onValueChange={(value) => handleGroupChange(user.email, value)}
                    >
                      {groups.map((group) => (
                        <MultiSelectItem key={group.id} value={group.name}>
                          {group.name}
                        </MultiSelectItem>
                      ))}
                    </MultiSelect>
                  </TableCell>
                  <TableCell className="text-right">
                    <Text>{user.created_at}</Text>
                  </TableCell>
                  <TableCell className="text-right">
                    <Text>{user.last_login}</Text>
                  </TableCell>
                  <TableCell>
                    <UsersMenu user={user} currentUser={currentUser} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
      <AddUserModal
        isOpen={isAddUserModalOpen}
        onClose={() => setAddUserModalOpen(false)}
        authType={authType}
        mutateUsers={mutateUsers}
        accessToken={accessToken}
      />
    </div>
  );
}
