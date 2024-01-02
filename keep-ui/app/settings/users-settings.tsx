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
} from "@tremor/react";
import Loading from "app/loading";
import useSWR, { mutate } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import Image from "next/image";
import { User } from "./models";
import UsersMenu from "./users-menu";
import { User as AuthUser } from "next-auth";
import { UserPlusIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import AddUserModal from './add-user-modal';
import { AuthenticationType } from "utils/authenticationType";

interface Props {
  accessToken: string;
  currentUser?: AuthUser;
  selectedTab: string;
}
interface Config {
  AUTH_TYPE: string;
}

export default function UsersSettings({
  accessToken,
  currentUser,
  selectedTab,
}: Props) {
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<User[]>(
    selectedTab === "users" ? `${apiUrl}/settings/users` : null,
    async (url) => {
      const response = await fetcher(url, accessToken);
      setUsers(response); // Update users state
      return response;
    },
    { revalidateOnFocus: false }
  );


  const { data: configData } = useSWR<Config>("/api/config", fetcher, {
    revalidateOnFocus: false,
  });

  const [isAddUserModalOpen, setAddUserModalOpen] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [addUserError, setAddUserError] = useState('');


  // Determine runtime configuration
  const authType = configData?.AUTH_TYPE as AuthenticationType;

  if (!data || isLoading) return <Loading />;


  return (
    <div className="mt-10">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>Users Management</Title>
          <Subtitle>Add or remove users from your tenant</Subtitle>
          {addUserError && (
            <div className="text-red-500 text-center mt-2">{addUserError}</div> // Display error message
          )}
        </div>
        <div>
          <Button
            color="orange"
            size="md"
            icon={UserPlusIcon}
            onClick={() => setAddUserModalOpen(true)}
          >
            Add User
          </Button>
        </div>
      </div>
      <Card className="mt-2.5">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>{/** Image */}</TableHeaderCell>
              <TableHeaderCell>{authType == AuthenticationType.MULTI_TENANT? "Email": "Username"}</TableHeaderCell>
              <TableHeaderCell className="text-right">Name</TableHeaderCell>
              <TableHeaderCell className="text-right">Role</TableHeaderCell>
              <TableHeaderCell className="text-right">
                Created At
              </TableHeaderCell>
              <TableHeaderCell className="text-right">
                Last Login
              </TableHeaderCell>
              <TableHeaderCell>{/**Menu */}</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((user) => (
              <TableRow
                key={user.name}
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
                <TableCell>{user.email}</TableCell>
                <TableCell className="text-right">
                  <Text>{user.name}</Text>
                </TableCell>
                <TableCell className="text-right">
                  <Text>{user.role}</Text>
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
      </Card>
      <AddUserModal
        isOpen={isAddUserModalOpen}
        onClose={() => setAddUserModalOpen(false)}
        authType={authType}
        setUsers={setUsers}
        accessToken={accessToken}
      />
    </div>
  );
}
