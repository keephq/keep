import { TableBody, TableRow, TableCell } from "@tremor/react";
import { AlertDto } from "@/entities/alerts/model";
import Skeleton from "react-loading-skeleton";
import "react-loading-skeleton/dist/skeleton.css";
import { Table } from "@tanstack/react-table";
import React, { useState } from "react";
import PushAlertToServerModal from "./alert-push-alert-to-server-modal";
import { EmptyStateCard } from "@/components/ui/EmptyStateCard";
import { MagnifyingGlassIcon, FunnelIcon } from "@heroicons/react/24/outline";
import { GroupedRow } from "./alert-grouped-row";
import { ViewedAlert } from "./alert-table";

interface Props {
  table: Table<AlertDto>;
  showSkeleton: boolean;
  showEmptyState: boolean;
  showFilterEmptyState?: boolean;
  showSearchEmptyState?: boolean;
  theme: { [key: string]: string };
  onRowClick: (alert: AlertDto) => void;
  onClearFiltersClick?: () => void;
  presetName: string;
  viewedAlerts: ViewedAlert[];
  lastViewedAlert: string | null;
}

export function AlertsTableBody({
  table,
  showSkeleton,
  showEmptyState,
  theme,
  onRowClick,
  onClearFiltersClick,
  presetName,
  showFilterEmptyState,
  showSearchEmptyState,
  viewedAlerts,
  lastViewedAlert,
}: Props) {
  const [modalOpen, setModalOpen] = useState(false);

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
    // Prevent row click when clicking on specified elements
    if (
      (e.target as HTMLElement).closest(
        "button, .menu, input, a, span, .prevent-row-click"
      )
    ) {
      return;
    }

    const rowElement = e.currentTarget as HTMLElement;
    if (rowElement.classList.contains("menu-open")) {
      return;
    }

    onRowClick(alert);
  };

  if (showSkeleton) {
    return (
      <TableBody>
        {Array(20)
          .fill("")
          .map((index, rowIndex) => (
            <TableRow key={`row-${index}-${rowIndex}`}>
              {table.getAllColumns().map((c, cellIndex) => (
                <TableCell
                  key={`cell-${c.id}-${cellIndex}`}
                  className={c.columnDef.meta?.tdClassName}
                >
                  <Skeleton containerClassName="w-full" />
                </TableCell>
              ))}
            </TableRow>
          ))}
      </TableBody>
    );
  }

  return (
    <TableBody>
      {table.getRowModel().rows.map((row) => (
        <GroupedRow
          key={row.id}
          row={row}
          table={table}
          theme={theme}
          onRowClick={handleRowClick}
          viewedAlerts={viewedAlerts}
          lastViewedAlert={lastViewedAlert}
        />
      ))}
    </TableBody>
  );
}
