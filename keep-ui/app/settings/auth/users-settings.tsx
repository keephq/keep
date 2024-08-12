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
  Badge,
  TextInput,
} from "@tremor/react";
import Loading from "app/loading";
import Image from "next/image";
import { User as AuthUser } from "next-auth";
import { TrashIcon } from "@heroicons/react/24/outline";
import { TiUserAdd } from "react-icons/ti";
import { useState, useEffect, useMemo } from "react";
import { AuthenticationType } from "utils/authenticationType";
import { useUsers } from "utils/hooks/useUsers";
import { useRoles } from "utils/hooks/useRoles";
import { useGroups } from "utils/hooks/useGroups";
import { useConfig } from "utils/hooks/useConfig";
import UsersSidebar from "./users-sidebar";
import { getInitials } from "components/navbar/UserInfo";
import { User } from "app/settings/models";
import { getApiURL } from "utils/apiUrl";

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
  const { data: users, isLoading, mutate: mutateUsers } = useUsers();
  const { data: roles = [] } = useRoles();
  const { data: groups } = useGroups();
  const { data: configData } = useConfig();

  const [userStates, setUserStates] = useState<{ [key: string]: { role: string, groups: string[] } }>({});
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [filter, setFilter] = useState("");
  const [isNewUser, setIsNewUser] = useState(false);

  // Determine runtime configuration
  const authType = configData?.AUTH_TYPE as AuthenticationType;
  const apiUrl = getApiURL();

  useEffect(() => {
    if (users) {
      const initialUserStates = users.reduce((acc, user) => {
        acc[user.email] = {
          role: user.role,
          groups: user.groups ? user.groups.map(group => group.name) : [],
        };
        return acc;
      }, {} as { [key: string]: { role: string, groups: string[] } });
      setUserStates(initialUserStates);
    }
  }, [users]);

  const filteredUsers = useMemo(() => {
    const filtered = users?.filter(user =>
      user.email.toLowerCase().includes(filter.toLowerCase())
    ) || [];

    return filtered.sort((a, b) => {
      // First, sort by last_login
      if (a.last_login && !b.last_login) return -1;
      if (!a.last_login && b.last_login) return 1;

      // If both have last_login or both don't have last_login, sort lexicographically
      return a.email.localeCompare(b.email);
    });
  }, [users, filter]);

  if (!users || isLoading || !roles || !groups) return <Loading />;

  const handleRowClick = (user: any) => {
    setSelectedUser(user);
    setIsNewUser(false);
    setIsSidebarOpen(true);
  };

  const handleAddUserClick = () => {
    setSelectedUser(null);
    setIsNewUser(true);
    setIsSidebarOpen(true);
  };

  const handleDeleteUser = async (userEmail: string, event: React.MouseEvent) => {
    event.stopPropagation();
    if (window.confirm("Are you sure you want to delete this user?")) {
      try {
        const url = `${getApiURL()}/auth/users/${userEmail}`;
        const response = await fetch(url, {
          method: 'DELETE',
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        });

        if (response.ok) {
          await mutateUsers();
        } else {
          console.error("Failed to delete user");
        }
      } catch (error) {
        console.error("Error deleting user:", error);
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
          <Table className="h-full">
            <TableHead>
              <TableRow>
                <TableHeaderCell className="w-1/24">{/** Image */}</TableHeaderCell>
                <TableHeaderCell className="w-2/12">
                  {authType == AuthenticationType.MULTI_TENANT || authType == AuthenticationType.KEYCLOAK
                    ? "Email"
                    : "Username"}
                </TableHeaderCell>
                <TableHeaderCell className="w-2/12">Name</TableHeaderCell>
                <TableHeaderCell className="w-2/12">Last Login</TableHeaderCell>
                <TableHeaderCell className="w-3/12">Role</TableHeaderCell>
                <TableHeaderCell className="w-3/12">Groups</TableHeaderCell>
                <TableHeaderCell className="w-1/12"></TableHeaderCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredUsers.map((user) => (
                <TableRow
                  key={user.email}
                  className={`${
                    user.email === currentUser?.email ? "bg-orange-50" : null
                  } hover:bg-gray-50 transition-colors duration-200 cursor-pointer group`}
                  onClick={() => handleRowClick(user)}
                >
                  <TableCell>
                    {user.picture ? (
                      <Image
                        className="rounded-full w-7 h-7 inline"
                        src={user.picture}
                        alt="user avatar"
                        width={28}
                        height={28}
                      />
                    ) : (
                      <span className="relative inline-flex items-center justify-center w-7 h-7 overflow-hidden bg-orange-400 rounded-full dark:bg-gray-600">
                        <span className="font-medium text-white text-xs">
                          {getInitials(user.name ?? user.email)}
                        </span>
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="w-2/12">
                    <div className="flex items-center justify-between">
                      <Text className="truncate">{user.email}</Text>
                      <div className="ml-2">
                        {user.ldap && (
                          <Badge color="orange">LDAP</Badge>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="w-2/12">
                    <Text>{user.name}</Text>
                  </TableCell>
                  <TableCell className="w-2/12">
                    <Text>{user.last_login ? new Date(user.last_login).toLocaleString() : "Never"}</Text>
                  </TableCell>
                  <TableCell className="w-3/12">
                    <div className="flex flex-wrap gap-1">
                      {userStates[user.email]?.role && (
                        <Badge color="orange" className="text-xs">
                          {userStates[user.email].role}
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="w-3/12">
                    <div className="flex flex-wrap gap-1">
                      {userStates[user.email]?.groups.slice(0, 4).map((group, index) => (
                        <Badge key={index} color="orange" className="text-xs">
                          {group}
                        </Badge>
                      ))}
                      {userStates[user.email]?.groups.length > 4 && (
                        <Badge color="orange" className="text-xs">
                          +{userStates[user.email].groups.length - 4} more
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="w-1/12">
                    {user.email !== currentUser?.email && !user.ldap && (
                      <div className="flex justify-end">
                        <Button
                          icon={TrashIcon}
                          variant="light"
                          color="orange"
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleDeleteUser(user.email, e)}
                        />
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </Card>
      <UsersSidebar
        isOpen={isSidebarOpen}
        toggle={() => setIsSidebarOpen(false)}
        user={selectedUser}
        isNewUser={isNewUser}
        mutateUsers={mutateUsers}
      />
    </div>
  );
}
