import React from "react";
import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Badge,
  Button,
  Text,
} from "@tremor/react";
import { TrashIcon } from "@heroicons/react/24/outline";
import { Permission } from "app/settings/models";

interface PermissionsTableProps {
  permissions: Permission[];
  onRowClick: (permission: Permission) => void;
  onDeletePermission: (resourceId: string, event: React.MouseEvent) => void;
  isDisabled?: boolean;
}

export function PermissionsTable({
  permissions,
  onRowClick,
  onDeletePermission,
  isDisabled = false,
}: PermissionsTableProps) {
  return (
    <Table className="h-full">
      <TableHead>
        <TableRow>
          <TableHeaderCell className="w-6/24">Resource Name</TableHeaderCell>
          <TableHeaderCell className="w-6/24">Resource Type</TableHeaderCell>
          <TableHeaderCell className="w-11/24">Assigned To</TableHeaderCell>
          <TableHeaderCell className="w-1/24"></TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody className="overflow-auto">
        {permissions.map((permission) => (
          <TableRow
            key={permission.resource_id}
            className={`
              ${isDisabled ? "opacity-50" : "hover:bg-gray-50 cursor-pointer"}
              transition-colors duration-200 group
            `}
            onClick={() => !isDisabled && onRowClick(permission)}
          >
            <TableCell className="w-6/24">
              <div className="flex items-center justify-between">
                <Text className="truncate">{permission.name}</Text>
              </div>
            </TableCell>
            <TableCell className="w-6/24">
              <Badge color="orange" className="text-xs">
                {permission.type}
              </Badge>
            </TableCell>
            <TableCell className="w-11/24">
              <div className="flex flex-wrap gap-1">
                {permission.permissions?.slice(0, 5).map((perm, index) => (
                  <Badge key={index} color="orange" className="text-xs">
                    {perm.id}
                  </Badge>
                ))}
                {permission.permissions?.length > 5 && (
                  <Badge color="orange" className="text-xs">
                    +{permission.permissions.length - 5} more
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="w-1/24">
              {!isDisabled && (
                <Button
                  icon={TrashIcon}
                  variant="light"
                  color="orange"
                  className="opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={(e) => onDeletePermission(permission.resource_id, e)}
                />
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
