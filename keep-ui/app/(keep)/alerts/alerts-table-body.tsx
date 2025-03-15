import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import { Table, flexRender } from "@tanstack/react-table";
import React from "react";
import { GroupedRow } from "./alert-grouped-row";
import { useAlertRowStyle } from "@/entities/alerts/model/useAlertRowStyle";
import { getCommonPinningStylesAndClassNames } from "@/shared/ui";
import { getRowClassName, getCellClassName } from "./alert-table-utils";
import { useExpandedRows } from "utils/hooks/useExpandedRows";
import clsx from "clsx";
import "react-loading-skeleton/dist/skeleton.css";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
  theme: { [key: string]: string };
  onRowClick: (alert: AlertDto) => void;
  lastViewedAlert: string | null;
  presetName: string;
}

export function AlertsTableBody({
  table,
  showSkeleton,
  theme,
  onRowClick,
  lastViewedAlert,
  presetName,
}: Props) {
  const [rowStyle] = useAlertRowStyle();
  const { isRowExpanded } = useExpandedRows(presetName);

  const handleRowClick = (e: React.MouseEvent, alert: AlertDto) => {
    // Only prevent clicks on specific interactive elements
    const target = e.target as HTMLElement;
    const clickableElements = target.closest(
      'button, .menu, input, a, [role="button"], .prevent-row-click, .tremor-Select-root, .tremor-MultiSelect-root'
    );

    // Check if the click is on a menu or if the element is marked as clickable
    if (clickableElements || target.classList.contains("menu-open")) {
      return;
    }

    onRowClick(alert);
  };

  if (showSkeleton) {
    return (
      <TableBody>
        {Array.from({ length: 20 }).map((_, index) => (
          <TableRow
            key={index}
            className={getRowClassName(
              { id: index.toString(), original: {} as AlertDto },
              theme,
              lastViewedAlert,
              rowStyle
            )}
          >
            {Array.from({ length: 7 }).map((_, cellIndex) => (
              <TableCell
                key={cellIndex}
                className={getCellClassName(
                  {
                    column: {
                      id: cellIndex.toString(),
                      columnDef: { meta: { tdClassName: "" } },
                    },
                  },
                  "",
                  rowStyle,
                  false
                )}
              >
                <div className="h-4 bg-gray-200 rounded animate-pulse mx-0.5" />
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    );
  }

  // This trick handles cases when rows have duplicated ids
  // It shouldn't happen, but the API currently returns duplicated ids
  // And in order to mitigate this issue, we append the rowIndex to the key for duplicated keys
  const visitedIds = new Set<string>();

  return (
    <TableBody>
      {table.getRowModel().rows.map((row, rowIndex) => {
        let renderingKey = row.id;

        if (visitedIds.has(renderingKey)) {
          renderingKey = `${renderingKey}-${rowIndex}`;
        } else {
          visitedIds.add(renderingKey);
        }

        if (row.getIsGrouped()) {
          return (
            <GroupedRow
              key={renderingKey}
              row={row}
              table={table}
              theme={theme}
              onRowClick={handleRowClick}
              lastViewedAlert={lastViewedAlert}
              rowStyle={rowStyle}
            />
          );
        }

        const isLastViewed = row.original.fingerprint === lastViewedAlert;
        const expanded = isRowExpanded(row.original.fingerprint);

        return (
          <TableRow
            key={renderingKey}
            className={clsx(
              "group/row",
              // Using tailwind classes for expanded rows instead of a custom class
              expanded ? "!h-auto min-h-12" : null,
              getRowClassName(row, theme, lastViewedAlert, rowStyle, expanded)
            )}
            onClick={(e) => handleRowClick(e, row.original)}
          >
            {row.getVisibleCells().map((cell) => {
              const { style, className } = getCommonPinningStylesAndClassNames(
                cell.column,
                table.getState().columnPinning.left?.length,
                table.getState().columnPinning.right?.length
              );

              const isNameCell = cell.column.id === "name";
              const isDescriptionCell = cell.column.id === "description";
              const isSourceCell = cell.column.id === "source";
              const expanded = isRowExpanded(row.original.fingerprint);

              return (
                <TableCell
                  key={cell.id}
                  data-column-id={cell.column.id}
                  className={clsx(
                    getCellClassName(
                      cell,
                      className,
                      rowStyle,
                      isLastViewed,
                      expanded
                    ),
                    // Force padding when expanded but not for source column
                    expanded && !isSourceCell ? "!p-3" : null,
                    // Source cell needs specific treatment when expanded
                    expanded && isSourceCell
                      ? "!p-0 !w-8 !min-w-8 !max-w-8 flex items-center justify-center !h-full"
                      : null,
                    // Name cell specific classes when expanded
                    expanded && isNameCell
                      ? "!max-w-[180px] w-[180px] !overflow-hidden"
                      : null,
                    // Description cell specific classes when expanded
                    expanded && isDescriptionCell
                      ? "!whitespace-pre-wrap !break-words w-auto"
                      : null
                  )}
                  style={{
                    ...style,
                    // For source cells, enforce fixed width always
                    ...(isSourceCell
                      ? {
                          width: "32px",
                          minWidth: "32px",
                          maxWidth: "32px",
                          padding: 0,
                        }
                      : {}),
                    // For name cells when expanded, use strict fixed width
                    ...(expanded && isNameCell
                      ? {
                          width: "180px",
                          maxWidth: "180px",
                          minWidth: "180px",
                          overflow: "hidden",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                        }
                      : {}),
                    // For description cells when expanded
                    ...(expanded && isDescriptionCell
                      ? {
                          width: "auto",
                          minWidth: "200px",
                          whiteSpace: "pre-wrap",
                          wordBreak: "break-word",
                          overflow: "visible",
                        }
                      : {}),
                  }}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              );
            })}
          </TableRow>
        );
      })}
    </TableBody>
  );
}
