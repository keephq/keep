import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto, Severity } from "@/entities/alerts/model"; // Make sure to import Severity
import { Table, flexRender, Row } from "@tanstack/react-table";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useState } from "react";

interface GroupedRowProps {
  row: Row<AlertDto>;
  table: Table<AlertDto>;
  theme: Record<string, string>;
  onRowClick?: (alert: AlertDto) => void;
  depth?: number;
}

export const GroupedRow = ({
  row,
  table,
  theme,
  onRowClick,
}: GroupedRowProps) => {
  const [isExpanded, setIsExpanded] = useState(true);

  console.log("Row info:", {
    id: row.id,
    isGrouped: row.getIsGrouped(),
    groupingColumnId: row.groupingColumnId,
    subRows: row.subRows.length,
    depth: row.depth,
  });

  if (row.getIsGrouped()) {
    // Safely get the group value
    const groupingColumnId = row.groupingColumnId;
    const groupValue = groupingColumnId
      ? row.getValue(groupingColumnId)
      : "Unknown Group";

    return (
      <>
        {/* Group Header Row */}
        <TableRow className="bg-gray-100 hover:bg-gray-200 cursor-pointer border-t border-gray-300">
          <TableCell
            colSpan={row.getVisibleCells().length}
            onClick={() => setIsExpanded(!isExpanded)}
          >
            <div className="flex items-center gap-2 py-2 px-4">
              <ChevronDownIcon
                className={clsx(
                  "w-5 h-5 transition-transform",
                  !isExpanded && "-rotate-90"
                )}
              />
              <div className="flex items-center gap-2">
                <span className="font-medium">{String(groupValue)}</span>
                <span className="text-gray-500 text-sm">
                  ({row.subRows.length}{" "}
                  {row.subRows.length === 1 ? "item" : "items"})
                </span>
              </div>
            </div>
          </TableCell>
        </TableRow>

        {/* Child Rows */}
        {isExpanded && (
          <TableRow>
            <TableCell
              colSpan={row.getVisibleCells().length}
              className="p-0 border-none"
            >
              <div className="border-l-2 border-gray-200 ml-6">
                {row.subRows.map((subRow) => (
                  <TableRow
                    key={subRow.id}
                    className={clsx(
                      "hover:bg-gray-50 cursor-pointer",
                      theme[subRow.original.severity as Severity],
                      subRow.getIsSelected() && "bg-blue-50 hover:bg-blue-100"
                    )}
                    onClick={() => onRowClick?.(subRow.original)}
                  >
                    {subRow.getVisibleCells().map((cell) => (
                      <TableCell key={cell.id}>
                        {flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </div>
            </TableCell>
          </TableRow>
        )}
      </>
    );
  }

  // Regular non-grouped row
  return (
    <TableRow
      className={clsx(
        "hover:bg-gray-50 cursor-pointer",
        theme[row.original.severity as Severity],
        row.getIsSelected() && "bg-blue-50 hover:bg-blue-100"
      )}
      onClick={() => onRowClick?.(row.original)}
    >
      {row.getVisibleCells().map((cell) => (
        <TableCell key={cell.id}>
          {flexRender(cell.column.columnDef.cell, cell.getContext())}
        </TableCell>
      ))}
    </TableRow>
  );
};
