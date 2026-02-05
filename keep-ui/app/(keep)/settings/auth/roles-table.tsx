import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Badge,
  Button,
} from "@tremor/react";
import { TrashIcon } from "@heroicons/react/24/outline";
import { Role } from "@/app/(keep)/settings/models";

interface RolesTableProps {
  roles: Role[];
  onRowClick: (role: Role) => void;
  onDeleteRole: (roleId: string, event: React.MouseEvent) => void;
  isDisabled?: boolean;
}

export function RolesTable({
  roles,
  onRowClick,
  onDeleteRole,
  isDisabled = false,
}: RolesTableProps) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell className="w-4/24">Role Name</TableHeaderCell>
          <TableHeaderCell className="w-4/24">Description</TableHeaderCell>
          <TableHeaderCell className="w-15/24">Scopes</TableHeaderCell>
          <TableHeaderCell className="w-1/24"></TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {roles
          .sort((a, b) =>
            a.predefined === b.predefined ? 0 : a.predefined ? -1 : 1
          )
          .map((role) => (
            <TableRow
              key={role.name}
              className={`
              ${isDisabled ? "opacity-50" : "hover:bg-gray-50 cursor-pointer"}
              transition-colors duration-200 group
            `}
              onClick={() => !isDisabled && onRowClick(role)}
            >
              <TableCell className="w-4/24">
                <div className="flex items-center justify-between">
                  <Text className="truncate">{role.name}</Text>
                  <div className="flex items-center">
                    {role.predefined ? (
                      <Badge color="orange" className="ml-2 w-24 text-center">
                        Predefined
                      </Badge>
                    ) : (
                      <Badge color="orange" className="ml-2 w-24 text-center">
                        Custom
                      </Badge>
                    )}
                  </div>
                </div>
              </TableCell>
              <TableCell className="w-4/24">
                <Text>{role.description}</Text>
              </TableCell>
              <TableCell className="w-15/24">
                <div className="flex flex-wrap gap-1">
                  {role.scopes.slice(0, 4).map((scope, index) => (
                    <Badge key={index} color="orange" className="text-xs">
                      {scope}
                    </Badge>
                  ))}
                  {role.scopes.length > 4 && (
                    <Badge color="orange" className="text-xs">
                      +{role.scopes.length - 4} more
                    </Badge>
                  )}
                </div>
              </TableCell>
              <TableCell className="w-1/24">
                {!isDisabled && !role.predefined && (
                  <Button
                    icon={TrashIcon}
                    variant="light"
                    color="orange"
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => onDeleteRole(role.id, e)}
                  />
                )}
              </TableCell>
            </TableRow>
          ))}
      </TableBody>
    </Table>
  );
}
