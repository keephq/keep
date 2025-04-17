import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Button,
  Badge,
} from "@tremor/react";
import Image from "next/image";
import { TrashIcon } from "@heroicons/react/24/outline";
import { AuthType } from "utils/authenticationType";
import { User } from "@/app/(keep)/settings/models";
import UserAvatar, { getInitials } from "@/components/navbar/UserAvatar";

interface UsersTableProps {
  users: User[];
  currentUserEmail?: string;
  authType: AuthType;
  onRowClick?: (user: User) => void;
  onDeleteUser?: (email: string, event: React.MouseEvent) => void;
  isDisabled?: boolean;
  groupsAllowed?: boolean;
  userCreationAllowed?: boolean;
}

export function UsersTable({
  users,
  currentUserEmail,
  authType,
  onRowClick,
  onDeleteUser,
  isDisabled = false,
  groupsAllowed = true,
  userCreationAllowed = true,
}: UsersTableProps) {
  return (
    <Table>
      <TableHead>
        <TableRow className="border-b border-tremor-border dark:border-dark-tremor-border">
          <TableHeaderCell className="w-3/12">
            {authType === AuthType.AUTH0 || authType === AuthType.KEYCLOAK
              ? "Email"
              : "Username"}
          </TableHeaderCell>
          <TableHeaderCell className="w-2/12">Name</TableHeaderCell>
          <TableHeaderCell className="w-1/12">Role</TableHeaderCell>
          {groupsAllowed && (
            <TableHeaderCell className="w-3/12">Groups</TableHeaderCell>
          )}
          <TableHeaderCell className="w-2/12">Last Login</TableHeaderCell>
          <TableHeaderCell className="w-1/12"></TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {users.map((user) => (
          <TableRow
            key={user.email}
            className={`
              ${user.email === currentUserEmail ? "bg-orange-50" : ""}
              ${isDisabled ? "opacity-50" : "hover:bg-gray-50 cursor-pointer"}
              transition-colors duration-200 group
            `}
            onClick={() => !isDisabled && onRowClick && onRowClick(user)}
          >
            <TableCell className="w-3/12">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <UserAvatar
                    image={user.picture}
                    name={user.name ?? user.email}
                    email={user.email}
                    size="sm"
                  />
                  <Text className="truncate">{user.email}</Text>
                </div>
                <div className="ml-2">
                  {user.ldap && <Badge color="orange">LDAP</Badge>}
                </div>
              </div>
            </TableCell>
            <TableCell className="w-2/12">
              <Text>{user.name}</Text>
            </TableCell>
            <TableCell className="w-2/12">
              <div className="flex flex-wrap gap-1">
                {user.role && (
                  <Badge color="orange" className="text-xs">
                    {user.role}
                  </Badge>
                )}
              </div>
            </TableCell>
            {groupsAllowed && (
              <TableCell className="w-2/12">
                <div className="flex flex-wrap gap-1">
                  {user.groups?.slice(0, 4).map((group, index) => (
                    <Badge key={index} color="orange" className="text-xs">
                      {group.name}
                    </Badge>
                  ))}
                  {user.groups && user.groups.length > 4 && (
                    <Badge color="orange" className="text-xs">
                      +{user.groups.length - 4} more
                    </Badge>
                  )}
                </div>
              </TableCell>
            )}
            <TableCell className="w-2/12">
              <Text>
                {user.last_login
                  ? new Date(user.last_login).toLocaleString()
                  : "Never"}
              </Text>
            </TableCell>
            <TableCell className="w-1/12">
              {!isDisabled &&
                user.email !== currentUserEmail &&
                !user.ldap &&
                userCreationAllowed && (
                  <div className="flex justify-end">
                    <Button
                      icon={TrashIcon}
                      variant="light"
                      color="orange"
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) =>
                        onDeleteUser && onDeleteUser(user.email, e)
                      }
                    />
                  </div>
                )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
