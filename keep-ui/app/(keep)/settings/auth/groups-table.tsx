import React from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Badge,
  Button,
} from "@tremor/react";
import { TrashIcon } from "@heroicons/react/24/outline";

interface Group {
  id: string;
  name: string;
  members: string[];
  roles: string[];
}

interface GroupsTableProps {
  groups: Group[];
  onRowClick: (group: Group) => void;
  onDeleteGroup: (groupName: string, event: React.MouseEvent) => void;
  isDisabled?: boolean;
}

export function GroupsTable({
  groups,
  onRowClick,
  onDeleteGroup,
  isDisabled = false,
}: GroupsTableProps) {
  return (
    <Table>
      <TableHead>
        <TableRow>
          <TableHeaderCell className="w-3/24">Group Name</TableHeaderCell>
          <TableHeaderCell className="w-5/12">Members</TableHeaderCell>
          <TableHeaderCell className="w-5/12">Roles</TableHeaderCell>
          <TableHeaderCell className="w-1/24"></TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {groups.map((group) => (
          <TableRow
            key={group.id}
            className={`
              ${isDisabled ? "opacity-50" : "hover:bg-gray-50 cursor-pointer"}
              transition-colors duration-200 group
            `}
            onClick={() => !isDisabled && onRowClick(group)}
          >
            <TableCell className="w-2/12">{group.name}</TableCell>
            <TableCell className="w-4/12">
              <div className="flex flex-wrap gap-1">
                {group.members.slice(0, 4).map((member, index) => (
                  <Badge key={index} color="orange" className="text-xs">
                    {member}
                  </Badge>
                ))}
                {group.members.length > 4 && (
                  <Badge color="orange" className="text-xs">
                    +{group.members.length - 4} more
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="w-4/12">
              <div className="flex flex-wrap gap-1">
                {group.roles.slice(0, 4).map((role, index) => (
                  <Badge key={index} color="orange" className="text-xs">
                    {role}
                  </Badge>
                ))}
                {group.roles.length > 4 && (
                  <Badge color="orange" className="text-xs">
                    +{group.roles.length - 4} more
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
                  onClick={(e) => onDeleteGroup(group.name, e)}
                />
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
