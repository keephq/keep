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
} from "@tremor/react";
import { TrashIcon } from "@heroicons/react/24/outline";
import { Permission } from "app/settings/models";

interface PermissionsTableProps {
  presets: any[];
  displayPermissions: Permission[];
  selectedPermissions: { [key: string]: string[] };
  onRowClick: (preset: any) => void;
  onDeletePermission: (presetId: string, event: React.MouseEvent) => void;
  isDisabled?: boolean;
}

export function PermissionsTable({
  presets,
  displayPermissions,
  selectedPermissions,
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
          <TableHeaderCell className="w-11/24">Permissions</TableHeaderCell>
          <TableHeaderCell className="w-1/24"></TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody className="overflow-auto">
        {presets.map((preset) => (
          <TableRow
            key={preset.id}
            className={`
              ${isDisabled ? "opacity-50" : "hover:bg-gray-50 cursor-pointer"}
              transition-colors duration-200 group
            `}
            onClick={() => !isDisabled && onRowClick(preset)}
          >
            <TableCell className="w-6/24">{preset.name}</TableCell>
            <TableCell className="w-6/24">
              <Badge color="orange" className="text-xs">
                preset
              </Badge>
            </TableCell>
            <TableCell className="w-11/24">
              <div className="flex flex-wrap gap-1">
                {selectedPermissions[preset.id]
                  ?.slice(0, 5)
                  .map((permId, index) => (
                    <Badge key={index} color="orange" className="text-xs">
                      {displayPermissions.find((p) => p.id === permId)?.name}
                    </Badge>
                  ))}
                {selectedPermissions[preset.id]?.length > 5 && (
                  <Badge color="orange" className="text-xs">
                    +{selectedPermissions[preset.id].length - 5} more
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="w-1/24">
              {!isDisabled && (
                <div className="flex justify-end">
                  <Button
                    icon={TrashIcon}
                    variant="light"
                    color="orange"
                    className="opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => onDeletePermission(preset.id, e)}
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
