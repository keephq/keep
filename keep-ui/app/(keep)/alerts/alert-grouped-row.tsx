import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto, Severity } from "@/entities/alerts/model";
import { Table, flexRender, Row } from "@tanstack/react-table";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useState } from "react";
import {
  TableSeverityCell,
  UISeverity,
  getCommonPinningStylesAndClassNames,
} from "@/shared/ui";

interface GroupedRowProps {
  row: Row<AlertDto>;
  table: Table<AlertDto>;
  theme: Record<string, string>;
  onRowClick?: (e: React.MouseEvent, alert: AlertDto) => void;
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
          {/* Render a single cell that spans the entire width */}
          <TableCell
            colSpan={row.getVisibleCells().length}
            onClick={() => setIsExpanded(!isExpanded)}
            className="group-header-cell bg-orange-100 group-hover:bg-orange-200"
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
        </TableRow>

        {/* Child Rows */}
        {isExpanded &&
          row.subRows.map((subRow) => (
            <TableRow
              key={subRow.id}
              className={clsx(
                "hover:bg-gray-50 cursor-pointer group",
                theme[subRow.original.severity as Severity],
                subRow.getIsSelected() && "bg-blue-50 hover:bg-blue-100",
                "ml-4"
              )}
              onClick={(e) => onRowClick?.(e, subRow.original)}
            >
              {subRow.getVisibleCells().map((cell) => {
                const { style, className } =
                  getCommonPinningStylesAndClassNames(
                    cell.column,
                    table.getState().columnPinning.left?.length,
                    table.getState().columnPinning.right?.length
                  );

                const severity = row.original.severity || "info";
                const rowBgColor = theme[severity] || "bg-white";

                return (
                  <TableCell
                    key={cell.id}
                    className={clsx(
                      cell.column.columnDef.meta?.tdClassName,
                      className,
                      rowBgColor,
                      "group-hover:bg-orange-100"
                    )}
                    style={style}
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
  const severity = row.original.severity || "info";
  const rowBgColor = theme[severity] || "bg-white";
  return (
    <TableRow
      id={`alert-row-${row.original.fingerprint}`}
      key={row.id}
      className="cursor-pointer relative group"
      onClick={(e) => onRowClick?.(e, row.original)}
    >
      {row.getVisibleCells().map((cell) => {
        const { style, className } = getCommonPinningStylesAndClassNames(
          cell.column,
          table.getState().columnPinning.left?.length,
          table.getState().columnPinning.right?.length
        );
        return (
          <TableCell
            key={cell.id}
            className={clsx(
              cell.column.columnDef.meta?.tdClassName,
              className,
              rowBgColor,
              "group-hover:bg-orange-100"
            )}
            style={style}
          >
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </TableCell>
        );
      })}
    </TableRow>
  );
};

export default GroupedRow;
