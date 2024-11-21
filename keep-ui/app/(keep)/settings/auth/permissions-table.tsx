import React from "react";
import {
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Badge,
  Text,
} from "@tremor/react";

interface PermissionsTableProps {
  resources: any[];
  onRowClick: (resource: any) => void;
  isDisabled?: boolean;
}

export function PermissionsTable({
  resources,
  onRowClick,
  isDisabled = false,
}: PermissionsTableProps) {
  return (
    <Table className="h-full">
      <TableHead>
        <TableRow>
          <TableHeaderCell className="w-8/24">Resource Name</TableHeaderCell>
          <TableHeaderCell className="w-4/24">Resource Type</TableHeaderCell>
          <TableHeaderCell className="w-12/24">Assigned To</TableHeaderCell>
        </TableRow>
      </TableHead>
      <TableBody className="overflow-auto">
        {resources.map((resource) => (
          <TableRow
            key={resource.id}
            className={`
              ${isDisabled ? "opacity-50" : "hover:bg-gray-50 cursor-pointer"}
              transition-colors duration-200
            `}
            onClick={() => !isDisabled && onRowClick(resource)}
          >
            <TableCell className="w-8/24">
              <Text className="truncate">{resource.name}</Text>
            </TableCell>
            <TableCell className="w-4/24">
              <Badge color="orange" className="text-xs">
                {resource.type}
              </Badge>
            </TableCell>
            <TableCell className="w-12/24">
              <div className="flex flex-wrap gap-1">
                {resource.assignments.length > 0 ? (
                  <>
                    {resource.assignments
                      .slice(0, 5)
                      .map((assignment: string, index: number) => {
                        const [type, ...rest] = assignment.split("_");
                        const displayId = rest.join("_");
                        return (
                          <Badge key={index} color="orange" className="text-xs">
                            {`${displayId} (${type})`}
                          </Badge>
                        );
                      })}
                    {resource.assignments.length > 5 && (
                      <Badge color="orange" className="text-xs">
                        +{resource.assignments.length - 5} more
                      </Badge>
                    )}
                  </>
                ) : (
                  <Text className="text-gray-500 text-sm">No assignments</Text>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
