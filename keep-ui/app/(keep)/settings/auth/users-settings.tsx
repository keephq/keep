import React, { useState, useEffect, useMemo } from "react";
import { Title, Subtitle, Card, Button, TextInput } from "@tremor/react";
import Loading from "@/app/(keep)/loading";
import { User as AuthUser } from "next-auth";
import { TiUserAdd } from "react-icons/ti";
import { AuthType } from "utils/authenticationType";
import { useUsers } from "@/entities/users/model/useUsers";
import { useRoles } from "utils/hooks/useRoles";
import { useGroups } from "utils/hooks/useGroups";
import { useConfig } from "utils/hooks/useConfig";
import UsersSidebar from "./users-sidebar";
import { User } from "@/app/(keep)/settings/models";
import { UsersTable } from "./users-table";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast, ErrorComponent } from "@/shared/ui";

interface Props {
  currentUser?: AuthUser;
  groupsAllowed: boolean;
  userCreationAllowed: boolean;
}

export interface Config {
  AUTH_TYPE: string;
}

export default function UsersSettings({
  currentUser,
  groupsAllowed,
  userCreationAllowed,
}: Props) {
  const api = useApi();
  const { data: users, isLoading, error, mutate: mutateUsers } = useUsers();
  const { data: roles = [] } = useRoles();
  const { data: groups } = useGroups();
  const { data: configData } = useConfig();

  const [userStates, setUserStates] = useState<{
    [key: string]: { role: string; groups: string[] };
  }>({});
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [filter, setFilter] = useState("");
  const [isNewUser, setIsNewUser] = useState(false);
  // Determine runtime configuration
  const authType = configData?.AUTH_TYPE as AuthType;

  useEffect(() => {
    if (users) {
      const initialUserStates = users.reduce(
        (acc, user) => {
          acc[user.email] = {
            role: user.role,
            groups: user.groups ? user.groups.map((group) => group.name) : [],
          };
          return acc;
        },
        {} as { [key: string]: { role: string; groups: string[] } }
      );
      setUserStates(initialUserStates);
    }
  }, [users]);

  const filteredUsers = useMemo(() => {
    const filtered =
      users?.filter((user) =>
        user.email.toLowerCase().includes(filter.toLowerCase())
      ) || [];

    return filtered.sort((a, b) => {
      if (a.last_login && !b.last_login) return -1;
      if (!a.last_login && b.last_login) return 1;
      return a.email.localeCompare(b.email);
    });
  }, [users, filter]);

  if (error) {
    return <ErrorComponent error={error} />;
  }

  if ((!users || !roles || !groups) && !isLoading) {
    return <Loading />;
  }

  const handleRowClick = (user: User) => {
    setSelectedUser(user);
    setIsNewUser(false);
    setIsSidebarOpen(true);
  };

  const handleAddUserClick = () => {
    setSelectedUser(null);
    setIsNewUser(true);
    setIsSidebarOpen(true);
  };

  const handleDeleteUser = async (
    userEmail: string,
    event: React.MouseEvent
  ) => {
    event.stopPropagation();
    if (window.confirm("Are you sure you want to delete this user?")) {
      try {
        await api.delete(`/auth/users/${userEmail}`);

        await mutateUsers();
      } catch (error) {
        showErrorToast(error, "Failed to delete user");
      }
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex justify-between mb-4">
        <div className="flex flex-col">
          <Title>Users Management</Title>
          <Subtitle>Add or remove users from your tenant</Subtitle>
        </div>
        <div className="flex space-x-2">
          <Button
            color="orange"
            size="md"
            icon={TiUserAdd}
            onClick={handleAddUserClick}
            disabled={!userCreationAllowed}
            title={
              !userCreationAllowed
                ? "Users are managed externally and cannot be created from Keep"
                : undefined
            }
          >
            Add User
          </Button>
        </div>
      </div>
      <TextInput
        placeholder="Search by username"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        className="mb-4"
      />
      <Card className="flex-grow overflow-auto h-full">
        <div className="h-full w-full overflow-auto">
          <UsersTable
            users={filteredUsers}
            currentUserEmail={currentUser?.email ?? ""}
            authType={authType}
            onRowClick={handleRowClick}
            onDeleteUser={handleDeleteUser}
            groupsAllowed={groupsAllowed}
            userCreationAllowed={userCreationAllowed}
          />
        </div>
      </Card>
      <UsersSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        user={selectedUser ?? undefined}
        isNewUser={isNewUser}
        mutateUsers={mutateUsers}
        groupsEnabled={groupsAllowed}
        identifierType={authType === AuthType.DB ? "username" : "email"}
        userCreationAllowed={userCreationAllowed}
      />
    </div>
  );
}
