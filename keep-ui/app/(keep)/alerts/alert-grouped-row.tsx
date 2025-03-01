import { TableRow, TableCell, Icon } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import { Table, flexRender, Row } from "@tanstack/react-table";
import { ChevronDownIcon, EyeIcon } from "@heroicons/react/24/outline";
import clsx from "clsx";
import { useState } from "react";
import { getCommonPinningStylesAndClassNames } from "@/shared/ui";
import { ViewedAlert } from "./alert-table";
import { RowStyle } from "./RowStyleSelection";
import { format } from "date-fns";
import { getRowClassName, getCellClassName } from "./alert-table-utils";

interface GroupedRowProps {
  row: Row<AlertDto>;
  table: Table<AlertDto>;
  theme: Record<string, string>;
  onRowClick?: (e: React.MouseEvent, alert: AlertDto) => void;
  viewedAlerts: ViewedAlert[];
  lastViewedAlert: string | null;
  rowStyle: RowStyle;
}

export const GroupedRow = ({
  row,
  table,
  theme,
  onRowClick,
  viewedAlerts,
  lastViewedAlert,
  rowStyle,
}: GroupedRowProps) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (row.getIsGrouped()) {
    const groupingColumnId = row.groupingColumnId;
    const groupValue = groupingColumnId
      ? row.getValue(groupingColumnId)
      : "Unknown Group";

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
                {row.subRows.length === 1 ? "alert" : "alerts"})
              </span>
            </div>
          </TableCell>
        </TableRow>

        {/* Child Rows */}
        {isExpanded &&
          row.subRows.map((subRow) => {
            const viewedAlert = viewedAlerts?.find(
              (a) => a.fingerprint === subRow.original.fingerprint
            );
            const isLastViewed =
              subRow.original.fingerprint === lastViewedAlert;

            return (
              <TableRow
                key={subRow.id}
                className={getRowClassName(
                  subRow,
                  theme,
                  lastViewedAlert,
                  rowStyle
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

                  return (
                    <TableCell
                      key={cell.id}
                      className={getCellClassName(
                        cell,
                        className,
                        rowStyle,
                        isLastViewed
                      )}
                      style={style}
                    >
                      {viewedAlert && cell.column.id === "alertMenu" ? (
                        <div className="flex justify-end items-center gap-2">
                          <Icon
                            icon={EyeIcon}
                            tooltip={`Viewed ${format(
                              new Date(viewedAlert.viewedAt),
                              "MMM d, yyyy HH:mm"
                            )}`}
                          />
                          {flexRender(
                            cell.column.columnDef.cell,
                            cell.getContext()
                          )}
                        </div>
                      ) : (
                        flexRender(
                          cell.column.columnDef.cell,
                          cell.getContext()
                        )
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            );
          })}
      </>
    );
  }

  // Regular non-grouped row
  const viewedAlert = viewedAlerts?.find(
    (a) => a.fingerprint === row.original.fingerprint
  );
  const isLastViewed = row.original.fingerprint === lastViewedAlert;

  return (
    <TableRow
      id={`alert-row-${row.original.fingerprint}`}
      key={row.id}
      className={getRowClassName(row, theme, lastViewedAlert, rowStyle)}
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
            className={getCellClassName(
              cell,
              className,
              rowStyle,
              isLastViewed
            )}
            style={style}
          >
            {viewedAlert && cell.column.id === "alertMenu" ? (
              <div className="flex justify-end items-center gap-2">
                <Icon
                  icon={EyeIcon}
                  tooltip={`Viewed ${format(
                    new Date(viewedAlert.viewedAt),
                    "MMM d, yyyy HH:mm"
                  )}`}
                />
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </div>
            ) : (
              flexRender(cell.column.columnDef.cell, cell.getContext())
            )}
          </TableCell>
        );
      })}
    </TableRow>
  );
};

export default GroupedRow;
