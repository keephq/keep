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
import useSWR from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import Image from "next/image";
import { User } from "./models";
import UsersMenu from "./users-menu";
import { User as AuthUser } from "next-auth";
import { UserPlusIcon } from "@heroicons/react/24/outline";

interface Props {
  accessToken: string;
  currentUser?: AuthUser;
}

export default function UsersSettings({ accessToken, currentUser }: Props) {
  const apiUrl = getApiURL();
  const { data, error, isLoading } = useSWR<User[]>(
    `${apiUrl}/settings/users`,
    (url) => fetcher(url, accessToken)
  );

  if (!data || isLoading) return <Loading />;

  return (
    <div className="mt-10">
      <div className="flex justify-between">
        <div className="flex flex-col">
          <Title>Users Management</Title>
          <Subtitle>Add or remove users from your tenant</Subtitle>
        </div>
        <div>
          <Button color="orange" size="md" icon={UserPlusIcon}>
            Add User
          </Button>
        </div>
      </div>
      <Card className="mt-2.5">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>{/** Image */}</TableHeaderCell>
              <TableHeaderCell>Email</TableHeaderCell>
              <TableHeaderCell className="text-right">Name</TableHeaderCell>
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
            {data.map((user) => (
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
    </div>
  );
}
