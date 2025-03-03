import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import { Table, flexRender } from "@tanstack/react-table";
import React, { useState } from "react";
import PushAlertToServerModal from "./alert-push-alert-to-server-modal";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { MagnifyingGlassIcon, FunnelIcon } from "@heroicons/react/24/outline";
import { GroupedRow } from "./alert-grouped-row";
import { useAlertRowStyle } from "@/entities/alerts/model/useAlertRowStyle";
import { getCommonPinningStylesAndClassNames } from "@/shared/ui";
import { getRowClassName, getCellClassName } from "./alert-table-utils";
import clsx from "clsx";
import "react-loading-skeleton/dist/skeleton.css";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
  showFilterEmptyState?: boolean;
  showSearchEmptyState?: boolean;
  theme: { [key: string]: string };
  onRowClick: (alert: AlertDto) => void;
  onClearFiltersClick?: () => void;
  presetName: string;
  lastViewedAlert: string | null;
}

export function AlertsTableBody({
  table,
  showSkeleton,
  theme,
  onRowClick,
  onClearFiltersClick,
  presetName,
  showFilterEmptyState,
  showSearchEmptyState,
  lastViewedAlert,
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);
  const [rowStyle] = useAlertRowStyle();

  const handleModalClose = () => setModalOpen(false);
  const handleModalOpen = () => setModalOpen(true);

  if (!showSkeleton) {
    if (
      table.getPageCount() === 0 &&
      !showFilterEmptyState &&
      !showSearchEmptyState
    ) {
      return (
        <>
          <div className="flex items-center h-full w-full absolute -mt-20">
            <div className="flex flex-col justify-center items-center w-full p-4">
              <EmptyStateCard
                title="No alerts to display"
                description="It is because you have not connected any data source yet or there are no alerts matching the filter."
                buttonText="Add Alert"
                onClick={handleModalOpen}
              />
            </div>
          </div>
          {modalOpen && (
            <PushAlertToServerModal
              handleClose={handleModalClose}
              presetName={presetName}
            />
          )}
        </>
      );
    }

    if (showFilterEmptyState) {
      return (
        <>
          <div className="flex items-center h-full w-full absolute -mt-20">
            <div className="flex flex-col justify-center items-center w-full p-4">
              <EmptyStateCard
                title="No alerts to display matching your filter"
                buttonText="Reset filter"
                renderIcon={() => (
                  <FunnelIcon className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle" />
                )}
                onClick={() => onClearFiltersClick!()}
              />
            </div>
          </div>
        </>
      );
    }

    if (showSearchEmptyState) {
      return (
        <>
          <div className="flex items-center h-full w-full absolute -mt-20">
            <div className="flex flex-col justify-center items-center w-full p-4">
              <EmptyStateCard
                title="No alerts to display matching your CEL query"
                renderIcon={() => (
                  <MagnifyingGlassIcon className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle" />
                )}
              />
            </div>
          </div>
        </>
      );
    }
  }

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

  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => {
        if (row.getIsGrouped()) {
          return (
            <GroupedRow
              key={row.id}
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

        return (
          <TableRow
            key={row.id}
            className={clsx(
              "group/row",
              getRowClassName(row, theme, lastViewedAlert, rowStyle)
            )}
            onClick={(e) => handleRowClick(e, row.original)}
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
                  style={{
                    ...style,
                    maxWidth:
                      rowStyle === "default" && cell.column.id === "name"
                        ? "600px"
                        : undefined,
                  }}
                  title={
                    cell.column.id === "name" ? row.original.name : undefined
                  }
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
