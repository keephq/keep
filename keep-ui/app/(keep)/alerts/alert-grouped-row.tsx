import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto, Severity } from "@/entities/alerts/model";
import { Table, flexRender, Row } from "@tanstack/react-table";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useState } from "react";
import { TableSeverityCell, UISeverity } from "@/shared/ui";

interface GroupedRowProps {
  row: Row<AlertDto>;
  table: Table<AlertDto>;
  theme: Record<string, string>;
  onRowClick?: (alert: AlertDto) => void;
}

export const GroupedRow = ({
  row,
  table,
  theme,
  onRowClick,
}: GroupedRowProps) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (row.getIsGrouped()) {
    const groupingColumnId = row.groupingColumnId;
    const groupValue = groupingColumnId
      ? row.getValue(groupingColumnId)
      : "Unknown Group";

    const groupColumnIndex = row
      .getVisibleCells()
      .findIndex((cell) => cell.column.id === groupingColumnId);

    return (
      <>
        {/* Group Header Row */}
        <TableRow className="bg-orange-100 hover:bg-orange-200 cursor-pointer border-t border-orange-300">
          {row.getVisibleCells().map((cell, index) => {
            if (cell.column.id === "severity") {
              return <TableCell key={cell.id} className="w-1 !p-0 relative" />;
            }

            if (index === groupColumnIndex) {
              return (
                <TableCell
                  key={cell.id}
                  onClick={() => setIsExpanded(!isExpanded)}
                  className="group-header-cell"
                >
                  <div className="flex items-center gap-2">
                    <ChevronDownIcon
                      className={clsx(
                        "w-5 h-5 transition-transform",
                        !isExpanded && "-rotate-90"
                      )}
                    />
                    <span className="font-medium">{String(groupValue)}</span>
                    <span className="text-gray-500 text-sm">
                      ({row.subRows.length}{" "}
                      {row.subRows.length === 1 ? "item" : "items"})
                    </span>
                  </div>
                </TableCell>
              );
            }
            return <TableCell key={cell.id} />;
          })}
        </TableRow>

        {/* Child Rows */}
        {isExpanded &&
          row.subRows.map((subRow) => (
            <TableRow
              key={subRow.id}
              className={clsx(
                "hover:bg-gray-50 cursor-pointer",
                theme[subRow.original.severity as Severity],
                subRow.getIsSelected() && "bg-blue-50 hover:bg-blue-100",
                "ml-4"
              )}
              onClick={() => onRowClick?.(subRow.original)}
            >
              {subRow.getVisibleCells().map((cell) => {
                if (cell.column.id === "severity") {
                  return (
                    <TableCell key={cell.id} className="w-1 !p-0 relative">
                      <TableSeverityCell
                        severity={
                          subRow.original.severity as unknown as UISeverity
                        }
                      />
                    </TableCell>
                  );
                }
                return (
                  <TableCell
                    key={cell.id}
                    className={clsx(
                      cell.column.id === groupingColumnId && "pl-8"
                    )}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                );
              })}
            </TableRow>
          ))}
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
      {row.getVisibleCells().map((cell) => {
        if (cell.column.id === "severity") {
          return (
            <TableCell key={cell.id} className="w-1 !p-0 relative">
              <TableSeverityCell
                severity={row.original.severity as unknown as UISeverity}
              />
            </TableCell>
          );
        }
        return (
          <TableCell key={cell.id}>
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </TableCell>
        );
      })}
    </TableRow>
  );
};

export default GroupedRow;
